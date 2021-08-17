#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only

import re
from third_party import utils
from pleroma import Pleroma

def parse_args():
	parser = utils.arg_parser_factory(description='Generate and post a toot.')
	parser.add_argument(
		'-s', '--simulate', dest='simulate', action='store_true',
		help="Print the toot without actually posting it. Use this to make sure your bot's actually working.",
	)
	parser.add_argument(
		'-m', '--mode',
		default='markov',
		help='Pass one of these: ' + ', '.join(utils.TextGenerationMode.__members__),
	)
	return parser.parse_args()

PAIRED_PUNCTUATION = re.compile(r"[{}]".format(re.escape('[](){}"‘’“”«»„')))

async def main():
	args = parse_args()
	cfg = utils.load_config(args.cfg)

	toot = await utils.make_post(cfg, mode=utils.TextGenerationMode.__members__[args.mode])
	if cfg['strip_paired_punctuation']:
		toot = PAIRED_PUNCTUATION.sub("", toot)
	toot = toot.replace("@", "@\u200b")  # sanitize mentions
	toot = utils.remove_mentions(cfg, toot)

	if not args.simulate:
		async with Pleroma(api_base_url=cfg['site'], access_token=cfg['access_token']) as pl:
			try:
				await pl.post(toot, visibility='unlisted', cw=cfg['cw'])
			except Exception:
				import traceback
				toot = (
					'An error occurred while submitting the generated post. '
					'Contact io@csdisaster.club for assistance. Full traceback:\n\n'
					+ traceback.format_exc()
				)
				await pl.status_post(toot, visibility='unlisted', cw='Error!')
				raise

	try:
		print(toot)
	except UnicodeEncodeError:
		print(toot.encode("ascii", "ignore"))  # encode as ASCII, dropping any non-ASCII characters

if __name__ == '__main__':
	import anyio
	anyio.run(main)
