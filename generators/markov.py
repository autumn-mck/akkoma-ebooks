# SPDX-License-Identifier: MPL-2.0

import sqlite3
import markovify

def make_sentence(cfg):
	class nlt_fixed(markovify.NewlineText):  # modified version of NewlineText that never rejects sentences
		def test_sentence_input(self, sentence):
			return True  # all sentences are valid <3

	db = sqlite3.connect("toots.db")
	db.text_factory = str
	c = db.cursor()
	if cfg['learn_from_cw']:
		ignored_cws_query_params = "(" + ",".join("?" * len(cfg["ignored_cws"])) + ")"
		toots = c.execute(f"SELECT content FROM `toots` WHERE cw IS NULL OR CW NOT IN {ignored_cws_query_params} ORDER BY RANDOM() LIMIT 10000", cfg["ignored_cws"]).fetchall()
	else:
		toots = c.execute("SELECT content FROM `toots` WHERE cw IS NULL ORDER BY RANDOM() LIMIT 10000").fetchall()

	if len(toots) == 0:
		raise ValueError("Database is empty! Try running main.py.")

	nlt = markovify.NewlineText if cfg['overlap_ratio_enabled'] else nlt_fixed

	model = nlt("\n".join(toot[0].replace('\n', ' ') for toot in toots))

	db.close()

	if cfg['limit_length']:
		sentence_len = randint(cfg['length_lower_limit'], cfg['length_upper_limit'])

	sentence = None
	tries = 0
	for tries in range(10):
		if (sentence := model.make_short_sentence(
			max_chars=500,
			tries=10000,
			max_overlap_ratio=cfg['overlap_ratio'] if cfg['overlap_ratio_enabled'] else 0.7,
			max_words=sentence_len if cfg['limit_length'] else None
		)) is not None:
			break
	else:
		raise ValueError("Failed 10 times to produce a sentence!")

	return sentence
