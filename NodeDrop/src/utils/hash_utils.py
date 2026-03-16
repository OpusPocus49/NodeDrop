from __future__ import annotations

import hashlib
from pathlib import Path


DEFAULT_HASH_CHUNK_SIZE = 1024 * 1024  # 1 MB


def create_sha256_hasher() -> hashlib._Hash:
    """
    Create and return a new SHA-256 hash object.

    This helper centralizes the hashing algorithm used by NodeDrop V1.
    """
    return hashlib.sha256()


def update_sha256(hasher: hashlib._Hash, data: bytes) -> None:
    """
    Update an existing SHA-256 hasher with a bytes chunk.

    Args:
        hasher: Existing SHA-256 hash object.
        data: Raw bytes to add to the digest.

    Raises:
        TypeError: If data is not bytes-like.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("data must be bytes-like.")

    hasher.update(bytes(data))


def get_sha256_digest(hasher: hashlib._Hash) -> str:
    """
    Return the hexadecimal SHA-256 digest for an existing hasher.
    """
    return hasher.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """
    Compute the SHA-256 digest of a bytes object.
    """
    hasher = create_sha256_hasher()
    update_sha256(hasher, data)
    return get_sha256_digest(hasher)


def sha256_file(path: str | Path, chunk_size: int = DEFAULT_HASH_CHUNK_SIZE) -> str:
    """
    Compute the SHA-256 digest of a file.

    The file is read incrementally to avoid loading it entirely into memory.

    Args:
        path: Path to the file.
        chunk_size: Number of bytes read per iteration.

    Returns:
        Hexadecimal SHA-256 digest.

    Raises:
        FileNotFoundError: If the file does not exist.
        IsADirectoryError: If the path points to a directory.
        ValueError: If chunk_size is invalid.
    """
    file_path = Path(path)

    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0.")

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.is_file():
        raise IsADirectoryError(f"Path is not a file: {file_path}")

    hasher = create_sha256_hasher()

    with file_path.open("rb") as file_handle:
        while True:
            chunk = file_handle.read(chunk_size)
            if not chunk:
                break
            update_sha256(hasher, chunk)

    return get_sha256_digest(hasher)