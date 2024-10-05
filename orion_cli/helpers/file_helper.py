import hashlib
from pathlib import Path
from typing import Union

class FileHelper:
    @staticmethod
    async def is_plaintext(path: Union[str, Path]) -> bool:
        path = Path(path)
        buffer = path.read_bytes()
        try:
            buffer.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
    @staticmethod
    async def checksum(path: Union[str, Path]) -> str:
        path = Path(path)
        buffer = path.read_bytes()
        checksum = hashlib.md5(buffer).hexdigest()
        return checksum