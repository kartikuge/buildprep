from functools import lru_cache

from preptrack.storage.base import StorageBackend
from preptrack.storage.dynamo_local import DynamoLocalStorage


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    return DynamoLocalStorage()
