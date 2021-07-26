# SPDX-License-Identifier: AGPL-3.0-only

import anyio
from functools import wraps

def shield(f):
	@wraps(f)
	async def shielded(*args, **kwargs):
		with anyio.CancelScope(shield=True):
			return await f(*args, **kwargs)
	return shielded
