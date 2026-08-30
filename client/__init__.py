import contextlib

from .apiclient import BCRClient as pcrclient
from .apiclient import TWClient as tw_pcrclient
from .base import BaseClient
from .bilbili_login import *
from .playerpref import decryptxml, decrypt_access_key
from .request import *
from .response import LoadIndexResponse


async def check_client(client: BaseClient) -> LoadIndexResponse:
    for _ in range(3):
        with contextlib.suppress(Exception):
            return await client.load_index()
    return None
