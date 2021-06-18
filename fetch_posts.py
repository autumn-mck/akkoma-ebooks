#!/usr/bin/env python3
# SPDX-License-Identifier: EUPL-1.2

import re
import sys
import json
import anyio
import asqlite
import sqlite3
import asyncio
import aiohttp
import argparse
import functions
import contextlib
from http import HTTPStatus
from pleroma import Pleroma, http_session_factory

PATTERNS = {
	"handle": re.compile(r'^.*@(.+)'),
	"base_url": re.compile(r'https?:\/\/(.*)'),
	"webfinger_template_url": re.compile(r'template="([^"]+)"'),
	"post_id": re.compile(r'[^\/]+$'),
}

@contextlib.asynccontextmanager
async def get_db():
	async with asqlite.connect('toots.db') as conn:
		async with conn.cursor() as cur:
			await cur.execute("""
				CREATE TABLE IF NOT EXISTS toots (
					sortid INTEGER UNIQUE PRIMARY KEY AUTOINCREMENT,
					id VARCHAR NOT NULL,
					cw VARCHAR,
					userid VARCHAR NOT NULL,
					uri VARCHAR NOT NULL,
					content VARCHAR NOT NULL
				)
			""")
			await cur.execute("""
				CREATE TABLE IF NOT EXISTS cursors (
					userid VARCHAR PRIMARY KEY,
					next_page VARCHAR NOT NULL
				)
			""")
			await cur.execute("""
				CREATE TRIGGER IF NOT EXISTS dedup
				AFTER INSERT ON toots
				FOR EACH ROW BEGIN
					DELETE FROM toots
					WHERE rowid NOT IN (
						SELECT MIN(sortid)
						FROM toots GROUP BY uri
					);
				END
			""")
			await conn.commit()
		yield conn

async def main():
	args = functions.parse_args(description='Log in and download posts.')
	cfg = functions.load_config(args.cfg)

	async with (
		Pleroma(api_base_url=cfg['site'], access_token=cfg['access_token']) as client,
		get_db() as db, db.cursor() as cur,
		http_session_factory() as http,
	):
		try:
			following = await client.following()
		except aiohttp.ClientResponseError as exc:
			if exc.status == HTTPStatus.FORBIDDEN:
				print(f'The provided access token in {args.cfg} is invalid.', file=sys.stderr)
				sys.exit(1)

		async with anyio.create_task_group() as tg:
			for acc in following:
				tg.start_soon(fetch_posts, cfg, http, cur, acc)

		print('Done!')

		await db.commit()
		await db.execute('VACUUM')  # compact db
		await db.commit()

async def fetch_posts(cfg, http, cur, acc):
	next_page = await (await cur.execute('SELECT next_page FROM cursors WHERE userid = ?', (acc['id'],))).fetchone()
	direction = 'next'
	if next_page is not None:
		next_page ,= next_page
		direction = 'prev'
	print('Downloading posts for user @' + acc['acct'])

	page = await fetch_first_page(cfg, http, acc, next_page)

	if 'next' not in page and 'prev' not in page:
		# there's only one page of results, don't bother doing anything special
		pass
	else:
		# this is for when we're all done. it points to the activities created *after* we started fetching.
		next_page = page['prev']

	print('Downloading and saving posts', end='', flush=True)
	done = False
	while not done and len(page['orderedItems']) > 0:
		try:
			async with anyio.create_task_group() as tg:
				for obj in page['orderedItems']:
					tg.start_soon(process_object, cur, acc, obj)
		except DoneWithAccount:
			done = True
			continue
		except anyio.ExceptionGroup as eg:
			for exc in eg.exceptions:
				if isinstance(exc, DoneWithAccount):
					done = True
					continue

		# get the next/previous page
		try:
			async with http.get(page[direction], timeout=15) as resp:
				page = await resp.json()
		except asyncio.TimeoutError:
			print('HTTP timeout, site did not respond within 15 seconds', file=sys.stderr)
		except KeyError:
			print("Couldn't get next page - we've probably got all the posts", file=sys.stderr)
		except KeyboardInterrupt:
			done = True
			break
		except aiohttp.ClientResponseError as exc:
			if exc.status == HTTPStatus.TOO_MANY_REQUESTS:
				print("We're rate limited. Skipping to next account.")
				done = True
				break
			raise
		except Exception:
			import traceback
			print('An error occurred while trying to obtain more posts:', file=sys.stderr)
			traceback.print_exc()

		print('.', end='', flush=True)
	else:
		# the while loop ran without breaking
		await cur.execute('REPLACE INTO cursors (userid, next_page) VALUES (?, ?)', (acc['id'], next_page))
		await cur.connection.commit()

	print(' Done!')

async def finger(cfg, http, acc):
	instance = PATTERNS['handle'].search(acc['acct'])
	if instance is None:
		instance = PATTERNS['base_url'].search(cfg['site'])[1]
	else:
		instance = instance[1]

	# 1. download host-meta to find webfinger URL
	async with http.get('https://{}/.well-known/host-meta'.format(instance), timeout=10) as resp:
		host_meta = await resp.text()

	# 2. use webfinger to find user's info page
	webfinger_url = PATTERNS['webfinger_template_url'].search(host_meta).group(1)
	webfinger_url = webfinger_url.format(uri='{}@{}'.format(acc['username'], instance))

	async with http.get(webfinger_url, headers={'Accept': 'application/json'}, timeout=10) as resp:
		profile = await resp.json()

	for link in profile['links']:
		if link['rel'] == 'self':
			# this is a link formatted like 'https://instan.ce/users/username', which is what we need
			return link['href']

	print("Couldn't find a valid ActivityPub outbox URL.", file=sys.stderr)
	sys.exit(1)

class DoneWithAccount(Exception): pass

async def process_object(cur, acc, obj):
	if obj['type'] != 'Create':
		# this isn't a toot/post/status/whatever, it's a boost or a follow or some other activitypub thing. ignore
		return

	# its a toost baby
	content = obj['object']['content']
	toot = extract_toot(content)
	try:
		await cur.execute('SELECT COUNT(*) FROM toots WHERE uri = ?', (obj['object']['id'],))
		existing = await cur.fetchone()
		if existing is not None and existing[0]:
			# we've caught up to the notices we've already downloaded, so we can stop now
			# you might be wondering, 'lynne, what if the instance ratelimits you after 40 posts, and they've made 60 since main.py was last run? wouldn't the bot miss 20 posts and never be able to see them?' to which i reply, 'i know but i don't know how to fix it'
			raise DoneWithAccount
		await insert_toot(cur, acc, obj, toot)
	except sqlite3.Error:
		pass  # ignore any toots that don't successfully go into the DB

async def fetch_first_page(cfg, http, acc, next_page):
	# download a page of the outbox
	if not next_page:
		print('Fingering UwU...')
		# find the user's activitypub outbox
		outbox_url = await finger(cfg, http, acc) + '/outbox?page=true'
	else:
		outbox_url = next_page

	async with http.get(outbox_url, timeout=15) as resp:
		return await resp.json()

def extract_toot(toot):
	toot = functions.extract_toot(toot)
	toot = toot.replace('@', '@\u200B')  # put a zws between @ and username to avoid mentioning
	return(toot)

async def insert_toot(cursor, acc, obj, content):
	post_id = PATTERNS['post_id'].search(obj['object']['id']).group(0)
	await cursor.execute('REPLACE INTO toots (id, cw, userid, uri, content) VALUES (?, ?, ?, ?, ?)', (
		post_id,
		obj['object']['summary'] or None,
		acc['id'],
		obj['object']['id'],
		content,
	))

if __name__ == '__main__':
	anyio.run(main)
