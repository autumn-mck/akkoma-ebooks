# SPDX-License-Identifier: EUPL-1.2

import sys
import aiohttp

USER_AGENT = (
	'pleroma-ebooks (https://github.com/ioistired/pleroma-ebooks); '
	'aiohttp/{aiohttp.__version__}; '
	'python/{py_version}'
)

def http_session_factory(headers={}):
	return aiohttp.ClientSession(
		headers={'User-Agent': USER_AGENT, **headers},
		raise_for_status=True,
	)

class Pleroma:
	def __init__(self, *, api_base_url, access_token):
		self.api_base_url = api_base_url.rstrip('/')
		py_version = '.'.join(map(str, sys.version_info))
		self._session = http_session_factory({'Authorization': 'Bearer ' + access_token})
		self._logged_in_id = None

	async def __aenter__(self):
		self._session = await self._session.__aenter__()
		return self

	async def __aexit__(self, *excinfo):
		return await self._session.__aexit__(*excinfo)

	async def request(self, method, path, **kwargs):
		async with self._session.request(method, self.api_base_url + path, **kwargs) as resp:
			return await resp.json()

	async def verify_credentials(self):
		return await self.request('GET', '/api/v1/accounts/verify_credentials')

	me = verify_credentials

	async def _get_logged_in_id(self):
		if self._logged_in_id is None:
			self._logged_in_id = (await self.me())['id']
		return self._logged_in_id

	async def following(self, account_id=None):
		account_id = account_id or await self._get_logged_in_id()
		return await self.request('GET', f'/api/v1/accounts/{account_id}/following')

	async def post(self, content, *, in_reply_to_id=None, cw=None, visibility=None):
		if visibility not in {None, 'private', 'public', 'unlisted', 'direct'}:
			raise ValueError('invalid visibility', visibility)

		if isinstance(in_reply_to_id, dict) and 'id' in in_reply_to_id:
			in_reply_to_id = in_reply_to_id['id']

		data = dict(status=content, in_reply_to_id=in_reply_to_id)
		if visibility is not None:
			data['visibility'] = visibility
		if cw is not None:
			data['spoiler_text'] = cw

		return await self.request('POST', '/api/v1/statuses', data=data)

	async def reply(self, to_status, content, *, cw=None):
		user_id = await self._get_logged_in_id()

		mentioned_accounts = {}
		mentioned_accounts[to_status['account']['id']] = to_status['account']['acct']
		for account in to_status['mentions']:
			if account['id'] != user_id and account['id'] not in mentioned_accounts:
				mentioned_accounts[account.id] = account.acct

		status = ''.join('@' + x + ' ' for x in mentioned_accounts.values()) + content

		visibility = to_status['visibility']
		if cw is None and 'spoiler_text' in to_status:
			cw = 're: ' + to_status['spoiler_text']

		return await self.post(content, in_reply_to_id=to_status['id'], cw=cw, visibility=visibility)
