import hashlib
from pathlib import Path
from typing import Callable, Iterable, Union
import zipfile
import gzip
from io import BytesIO


class FileHelper:
    @staticmethod
    def is_plaintext(path: Union[str, Path]) -> bool:
        path = Path(path)
        buffer = path.read_bytes()
        try:
            buffer.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    @staticmethod
    def checksum(path: Union[str, Path]) -> str:
        path = Path(path)
        buffer = path.read_bytes()
        checksum = hashlib.md5(buffer).hexdigest()
        return checksum

    @staticmethod
    def compress_buffer(
        buffer: BytesIO
    ) -> bytes:
        # Move the zip buffer to the beginning before reading
        buffer.seek(0)

        # In-memory bytes buffer for the gzip file
        gz_buffer = BytesIO()

        # Compress the zip file into a Gzip format in memory
        with gzip.GzipFile(fileobj=gz_buffer, mode="wb") as gz_file:
            gz_file.write(buffer.getvalue())

        # Move the gzip buffer to the beginning before returning
        gz_buffer.seek(0)

        # Return the gzip-compressed data as bytes
        return gz_buffer.getvalue()
