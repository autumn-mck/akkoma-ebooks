# akkoma-ebooks

This is a very slightly modified version of <https://github.com/ioistired/pleroma-ebooks>  
As I no longer use fedi or run any markov bots, this won't be updated any further (although it worked fine as-is)  
Changes:
- removes any generated @'s in replies to prevent accidentally mentioning somebody else on the same instance
- adds a config option to ban the specified words from appearing in generated posts

Original readme:

It's like [@AgathaSorceress's mstdn-ebooks] but it supports Pleroma better.

[@AgathaSorceress's mstdn-ebooks]: https://github.com/AgathaSorceress/mstdn-ebooks

## Secure Fetch
Secure fetch (aka authorised fetches, authenticated fetches, secure mode...) is *not* supported by pleroma-ebooks, and will fail to download any posts from users on instances with secure fetch enabled. For more information, see [this wiki page](https://github.com/Lynnesbian/mstdn-ebooks/wiki/Secure-fetch).

## Compatibility
| Software  | Downloading statuses                                              | Posting | Replying                                                    |
|-----------|-------------------------------------------------------------------|---------|-------------------------------------------------------------|
| Mastodon  | Yes                                                               | Yes     | Yes                                                         |
| Pleroma   | Yes                                                               | Yes     | Yes                                                         |
| Misskey   | Yes                                                               | No      | No                                                          |
| diaspora* | [No](https://github.com/diaspora/diaspora/issues/7422)            | No      | No                                                          |
| Others    | Maybe                                                             | No      | No                                                          |

*Note: Bots are only supported on Mastodon and Pleroma instances. Bots can learn from users on other instances, but the bot itself must run on either a Mastodon or Pleroma instance.*

pleroma-ebooks uses ActivityPub to download posts. This means that it is not dependant on any particular server software, and should work with anything that (properly) implements ActivityPub. Any software that does not support ActivityPub (e.g. diaspora*) is not supported, and won't work.

## Configuration
Configuring pleroma-ebooks is accomplished by editing `config.json`. If you want to use a different file for configuration, specify it with the `--cfg` argument. For example, if you want to use `/home/lynne/c.json` instead, you would run `python3 fetch_posts.py --cfg /home/lynne/c.json` instead of just `python3 fetch_posts.py`

| Setting                  | Default                                 | Meaning                                                                                                                                                                                                                                                                                 |
|--------------------------|-----------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| site                     | https://botsin.space                    | The instance your bot will log in to and post from. This must start with `https://` or `http://` (preferably the latter)                                                                                                                                                                |
| cw                       | null                                    | The content warning (aka subject) pleroma-ebooks will apply to non-error posts.                                                                                                                                                                                                           |
| learn_from_cw            | false                                   | If true, pleroma-ebooks will learn from CW'd posts.                                                                                                                                                                                                                                       |
| ignored_cws              | []                                      | If `learn_from_cw` is true, do not learn from posts with these CWs.
| mention_handling         | 1                                       | 0: Never use mentions. 1: Only generate fake mentions in the middle of posts, never at the start. 2: Use mentions as normal (old behaviour).                                                                                                                                            |
| max_thread_length        | 15                                      | The maximum number of bot posts in a thread before it stops replying. A thread can be 10 or 10000 posts long, but the bot will stop after it has posted `max_thread_length` times.                                                                                                      |
| strip_paired_punctuation | false                                   | If true, pleroma-ebooks will remove punctuation that commonly appears in pairs, like " and (). This avoids the issue of posts that open a bracket (or quote) without closing it.                                                                                                          |
| limit_length             | false                                   | If true, the sentence length will be random between `length_lower_limit` and `length_upper_limit`                                                                                                                                                                                       |
| length_lower_limit       | 5                                       | The lower bound in the random number range above. Only matters if `limit_length` is true.                                                                                                                                                                                               |
| length_upper_limit       | 50                                      | The upper bound in the random number range above. Can be the same as `length_lower_limit` to disable randomness. Only matters if `limit_length` is true.                                                                                                                                |
| overlap_ratio_enabled    | false                                   | If true, checks the output's similarity to the original posts.                                                                                                                                                                                                                          |
| overlap_ratio            | 0.7                                     | The ratio that determins if the output is too similar to original or not. With decreasing ratio, both the interestingness of the output and the likelihood of failing to create output increases. Only matters if `overlap_ratio_enabled` is true.                                      |
| banned_words             | [ ]                                     | an array of words to prevent from showing up (automatically includes plural versions of specified words)                           |

## Donating
Please don't feel obligated to donate at all.

- [Ko-Fi](https://ko-fi.com/lynnesbian) allows you to make one-off payments in increments of AU$3. These payments are not taxed.
- [PayPal](https://paypal.me/lynnesbian) allows you to make one-off payments of any amount in a range of currencies. These payments may be taxed.

## License

This is released under the AGPLv3 (only) license, and based on Lynnesbian's fork which is under the MPL 2.0 license. See LICENSE-AGPL.md and LICENSE-MPL for details.

**This means you must publish the source code of any ebooks bot you make with this.** A link back to this repository on your bot's profile page or profile metadata will suffice. If you make changes to the code you need to link to your fork/repo instead
