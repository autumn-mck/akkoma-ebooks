# SPDX-License-Identifier: AGPL-3.0-only

import anyio
import functools
from bs4 import BeautifulSoup

def shield(f):
	@functools.wraps(f)
	async def shielded(*args, **kwargs):
		with anyio.CancelScope(shield=True) as cs:
			return await f(*args, **kwargs)
	return shielded
