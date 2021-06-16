#!/usr/bin/env python3
# SPDX-License-Identifier: EUPL-1.2

from mastodon import Mastodon, MastodonUnauthorizedError
import sqlite3, signal, sys, json, re, argparse
import requests
import functions

parser = argparse.ArgumentParser(description='Log in and download posts.')
parser.add_argument(
										'-c', '--cfg', dest='cfg', default='config.json', nargs='?',
										help="Specify a custom location for config.json.")

args = parser.parse_args()

scopes = ["read:statuses", "read:accounts", "read:follows", "write:statuses", "read:notifications", "write:accounts"]
# cfg defaults

cfg = {
	"site": "https://botsin.space",
	"cw": None,
	"instance_blacklist": ["bofa.lol", "witches.town", "knzk.me"],  # rest in piece
	"learn_from_cw": False,
	"mention_handling": 1,
	"max_thread_length": 15,
	"strip_paired_punctuation": False,
	"limit_length": False,
	"length_lower_limit": 5,
	"length_upper_limit": 50,
	"overlap_ratio_enabled": False,
	"overlap_ratio": 0.7,
	"ignored_cws": [],
}

try:
	cfg.update(json.load(open(args.cfg, 'r')))
except FileNotFoundError:
	open(args.cfg, "w").write("{}")

print("Using {} as configuration file".format(args.cfg))

if not cfg['site'].startswith("https://") and not cfg['site'].startswith("http://"):
	print("Site must begin with 'https://' or 'http://'. Value '{}' is invalid - try 'https://{}' instead.".format(cfg['site']))
	sys.exit(1)

if "client" not in cfg:
	print("No application info -- registering application with {}".format(cfg['site']))
	client_id, client_secret = Mastodon.create_app(
		"mstdn-ebooks",
		api_base_url=cfg['site'],
		scopes=scopes,
		website="https://github.com/Lynnesbian/mstdn-ebooks")

	cfg['client'] = {
		"id": client_id,
		"secret": client_secret
	}

if "secret" not in cfg:
	print("No user credentials -- logging in to {}".format(cfg['site']))
	client = Mastodon(
		client_id=cfg['client']['id'],
		client_secret=cfg['client']['secret'],
		api_base_url=cfg['site'])

	print("Open this URL and authenticate to give mstdn-ebooks access to your bot's account: {}".format(client.auth_request_url(scopes=scopes)))
	cfg['secret'] = client.log_in(code=input("Secret: "), scopes=scopes)

json.dump(cfg, open(args.cfg, "w+"))


def extract_toot(toot):
	toot = functions.extract_toot(toot)
	toot = toot.replace("@", "@\u200B")  # put a zws between @ and username to avoid mentioning
	return(toot)


def get(*args, **kwargs):
	r = requests.get(*args, **kwargs)
	r.raise_for_status()
	return r


client = Mastodon(
	client_id=cfg['client']['id'],
	client_secret=cfg['client']['secret'],
	access_token=cfg['secret'],
	api_base_url=cfg['site'])

try:
	me = client.account_verify_credentials()
except MastodonUnauthorizedError:
	print("The provided access token in {} is invalid. Please delete {} and run main.py again.".format(args.cfg, args.cfg))
	sys.exit(1)

following = client.account_following(me.id)

db = sqlite3.connect("toots.db")
db.text_factory = str
c = db.cursor()
c.execute("CREATE TABLE IF NOT EXISTS toots (sortid INTEGER UNIQUE PRIMARY KEY AUTOINCREMENT, id VARCHAR NOT NULL, cw VARCHAR, userid VARCHAR NOT NULL, uri VARCHAR NOT NULL, content VARCHAR NOT NULL)")
c.execute("CREATE TABLE IF NOT EXISTS cursors (userid VARCHAR PRIMARY KEY, next_page VARCHAR NOT NULL)")
c.execute("CREATE TRIGGER IF NOT EXISTS dedup AFTER INSERT ON toots FOR EACH ROW BEGIN DELETE FROM toots WHERE rowid NOT IN (SELECT MIN(sortid) FROM toots GROUP BY uri ); END; ")
db.commit()


def handleCtrlC(signal, frame):
	print("\nPREMATURE EVACUATION - Saving chunks")
	db.commit()
	sys.exit(1)


signal.signal(signal.SIGINT, handleCtrlC)

patterns = {
	"handle": re.compile(r"^.*@(.+)"),
	"url": re.compile(r"https?:\/\/(.*)"),
	"uri": re.compile(r'template="([^"]+)"'),
	"pid": re.compile(r"[^\/]+$"),
}


def insert_toot(oii, acc, post, cursor):  # extracted to prevent duplication
	pid = patterns["pid"].search(oii['object']['id']).group(0)
	cursor.execute("REPLACE INTO toots (id, cw, userid, uri, content) VALUES (?, ?, ?, ?, ?)", (
		pid,
		oii['object']['summary'] or None,
		acc.id,
		oii['object']['id'],
		post
	))


for f in following:
	next_page = c.execute("SELECT next_page FROM cursors WHERE userid = ?", (f.id,)).fetchone()
	direction = 'next'
	if next_page is not None:
		next_page ,= next_page
		direction = 'prev'
	print(f'{next_page = }')
	print("Downloading posts for user @" + f.acct)

	# find the user's activitypub outbox
	print("WebFingering...")
	instance = patterns["handle"].search(f.acct)
	if instance is None:
		instance = patterns["url"].search(cfg['site']).group(1)
	else:
		instance = instance.group(1)

	if instance in cfg['instance_blacklist']:
		print("skipping blacklisted instance: {}".format(instance))
		continue

	try:
		# 1. download host-meta to find webfinger URL
		r = get("https://{}/.well-known/host-meta".format(instance), timeout=10)
		# 2. use webfinger to find user's info page
		uri = patterns["uri"].search(r.text).group(1)
		uri = uri.format(uri="{}@{}".format(f.username, instance))
		r = get(uri, headers={"Accept": "application/json"}, timeout=10)
		j = r.json()
		found = False
		for link in j['links']:
			if link['rel'] == 'self':
				# this is a link formatted like "https://instan.ce/users/username", which is what we need
				uri = link['href']
				found = True
				break
		if not found:
			print("Couldn't find a valid ActivityPub outbox URL.")

		# 3. download a page of the outbox
		uri = next_page or "{}/outbox?page=true".format(uri)
		r = get(uri, timeout=15)
		j = r.json()
	except:
		print("oopsy woopsy!! we made a fucky wucky!!!\n(we're probably rate limited, please hang up and try again)")
		sys.exit(1)

	if 'next' not in j and 'prev' not in j:
		# there's only one page of results, don't bother doing anything special
		pass
	else:
		# this is for when we're all done. it points to the activities created *after* we started fetching.
		next_page = j['prev']
		if next_page is None:
			uri = j[direction]
			r = get(uri)
			j = r.json()

	print("Downloading and saving posts", end='', flush=True)
	done = False
	try:
		while not done and len(j['orderedItems']) > 0:
			for oi in j['orderedItems']:
				if oi['type'] != "Create":
					continue  # this isn't a toot/post/status/whatever, it's a boost or a follow or some other activitypub thing. ignore

				# its a toost baby
				content = oi['object']['content']
				toot = extract_toot(content)
				# print(toot)
				try:
					if c.execute("SELECT COUNT(*) FROM toots WHERE uri LIKE ?", (oi['object']['id'],)).fetchone()[0] > 0:
						# we've caught up to the notices we've already downloaded, so we can stop now
						# you might be wondering, "lynne, what if the instance ratelimits you after 40 posts, and they've made 60 since main.py was last run? wouldn't the bot miss 20 posts and never be able to see them?" to which i reply, "i know but i don't know how to fix it"
						done = True
						continue
					if 'lang' in cfg:
						try:
							if oi['object']['contentMap'][cfg['lang']]:  # filter for language
								insert_toot(oi, f, toot, c)
						except KeyError:
							# JSON doesn't have contentMap, just insert the toot irregardlessly
							insert_toot(oi, f, toot, c)
					else:
						insert_toot(oi, f, toot, c)
				except KeyboardInterrupt:
					done = True
					break
				except sqlite3.Error:
					pass  # ignore any toots that don't successfully go into the DB

			# get the next/previous page
			try:
				r = get(j[direction], timeout=15)
			except requests.Timeout:
				print("HTTP timeout, site did not respond within 15 seconds")
			except KeyError:
				print("Couldn't get next page - we've probably got all the posts")
			except KeyboardInterrupt:
				done = True
				break
			except:
				print("An error occurred while trying to obtain more posts.")

			j = r.json()
			print('.', end='', flush=True)
		else:
			# the while loop ran without breaking
			c.execute("REPLACE INTO cursors (userid, next_page) VALUES (?, ?)", (f.id, next_page))
			db.commit()

		print(" Done!")
	except requests.HTTPError as e:
		if e.response.status_code == 429:
			print("Rate limit exceeded. This means we're downloading too many posts in quick succession. Saving toots to database and moving to next followed account.")
			db.commit()
		else:
			# TODO: remove duplicate code
			print("Encountered an error! Saving posts to database and moving to next followed account.")
			db.commit()
	except Exception:
		print("Encountered an error! Saving posts to database and moving to next followed account.")
		db.commit()

print("Done!")

db.commit()
db.execute("VACUUM")  # compact db
db.commit()
db.close()
