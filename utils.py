# SPDX-License-Identifier: AGPL-3.0-only

import anyio
from functools import wraps

def shield(f):
	@wraps(f)
	async def shielded(*args, **kwargs):
		with anyio.CancelScope(shield=True):
			return await f(*args, **kwargs)
	return shielded

def removeprefix(s, prefix):
	try:
		return s.removeprefix(prefix)
	except AttributeError:
		# compatibility for pre-3.9
		return s[len(prefix):] if s.startswith(prefix) else s
