# SPDX-License-Identifier: EUPL-1.2

import re
import os
import sys
import html
import enum
import json
import shutil
import sqlite3
import argparse
import itertools
import json5 as json
import multiprocessing
from random import randint
from bs4 import BeautifulSoup

TextGenerationMode = enum.Enum('TextGenerationMode', """
	markov
	gpt_2
""".split())

def arg_parser_factory(*, description):
	parser = argparse.ArgumentParser(description=description)
	parser.add_argument(
		'-c', '--cfg', dest='cfg', default='config.json', nargs='?',
		help='Specify a custom location for the config file.'
	)
	return parser

def parse_args(*, description):
	return arg_parser_factory(description=description).parse_args()

def load_config(cfg_path):
	with open('config.defaults.json') as f:
		cfg = json.load(f)

	with open(cfg_path) as f:
		cfg.update(json.load(f))

	if not cfg['site'].startswith('https://') and not cfg['site'].startswith('http://'):
		print("Site must begin with 'https://' or 'http://'. Value '{0}' is invalid - try 'https://{0}' instead.".format(cfg['site']), file=sys.stderr)
		sys.exit(1)

	if not cfg.get('access_token'):
		print('No authentication info', file=sys.stderr)
		print('Get a client id, client secret, and access token here: https://tools.splat.soy/pleroma-access-token/', file=sys.stderr)
		print('Then put `access_token` in your config file.', file=sys.stderr)
		sys.exit(1)

	cfg['generation_mode'] = TextGenerationMode.__members__[cfg['generation_mode']]

	return cfg

def remove_mention(cfg, sentence):
	# optionally remove mentions
	if cfg['mention_handling'] == 1:
		return re.sub(r"^\S*@\u200B\S*\s?", "", sentence)
	elif cfg['mention_handling'] == 0:
		sentence = re.sub(r"\S*@\u200B\S*\s?", "", sentence)

	return sentence

def _wrap_pipe(f):
	def g(pout, *args, **kwargs):
		try:
			pout.send(f(*args, **kwargs))
		except ValueError as exc:
			pout.send(exc.args[0])
	return g

def make_toot(cfg, *, mode=TextGenerationMode.markov):
	toot = None
	pin, pout = multiprocessing.Pipe(False)

	if mode is TextGenerationMode.markov:
		from generators.markov import make_sentence
	elif mode is TextGenerationMode.gpt_2:
		from generators.gpt_2 import make_sentence
	else:
		raise ValueError('Invalid text generation mode')

	p = multiprocessing.Process(target=_wrap_pipe(make_sentence), args=[pout, cfg])
	p.start()
	p.join(5)  # wait 5 seconds to get something
	if p.is_alive():  # if it's still trying to make a toot after 5 seconds
		p.terminate()
		p.join()
	else:
		toot = pin.recv()

	if toot is None:
		toot = 'Toot generation failed! Contact io@csdisaster.club for assistance.'
	return toot

def extract_post_content(text):
	soup = BeautifulSoup(text, "html.parser")
	for el in soup.select('br'):  # replace <br> with linebreak
		el.replace_with('\n')

	for ht in soup.select("a.hashtag, a.mention"):  # convert hashtags and mentions from links to text
		ht.unwrap()

	for link in soup.select("a"):  # convert <a href='https://example.com>example.com</a> to just https://example.com
		if 'href' in link:
			# apparently not all a tags have a href,
			# which is understandable if you're doing normal web stuff, but on a social media platform??
			link.replace_with(link["href"])

	for el in soup.select('p'):
		el.replace_with('\n' + el.get_text() + '\n')

	return soup.get_text().strip()
