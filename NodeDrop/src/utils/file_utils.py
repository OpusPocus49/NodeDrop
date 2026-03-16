from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO, Generator, Iterable

from core.models import TransferFile, TransferItemType


DEFAULT_FILE_CHUNK_SIZE = 64 * 1024
CHECKSUM_CHUNK_SIZE = 1024 * 1024


class FileUtilsError(Exception):
    """
    Base exception for filesystem utility failures.
    """


class FileWriteError(FileUtilsError):
    """
    Raised when a file cannot be opened or prepared for writing.
    """


def normalize_path(path: str | Path) -> Path:
    """
    Normalize a filesystem path safely.

    The returned path is absolute and resolved.
    """
    return Path(path).expanduser().resolve()


def compute_file_checksum(path: str | Path) -> str:
    """
    Compute the SHA256 checksum of a file.
    """
    file_path = normalize_path(path)

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    if not file_path.is_file():
        raise IsADirectoryError(file_path)

    sha256 = hashlib.sha256()

    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(CHECKSUM_CHUNK_SIZE)
            if not chunk:
                break
            sha256.update(chunk)

    return sha256.hexdigest()


def read_file_chunks(
    path: str | Path,
    chunk_size: int = DEFAULT_FILE_CHUNK_SIZE,
) -> Generator[bytes, None, None]:
    """
    Read a file incrementally and yield raw binary chunks.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0.")

    file_path = normalize_path(path)

    if not file_path.exists():
        raise FileNotFoundError(file_path)

    if not file_path.is_file():
        raise IsADirectoryError(file_path)

    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            yield chunk


def open_file_for_writing(path: str | Path) -> BinaryIO:
    """
    Open a file for binary writing, creating parent directories if needed.
    """
    file_path = Path(path)

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        return file_path.open("wb")
    except OSError as exc:
        raise FileWriteError(f"Unable to open file for writing: {file_path}") from exc


def walk_directory(root: str | Path) -> Generator[Path, None, None]:
    """
    Recursively yield files inside a directory, in deterministic order.
    """
    root_path = normalize_path(root)

    if not root_path.exists():
        raise FileNotFoundError(root_path)

    if not root_path.is_dir():
        raise NotADirectoryError(root_path)

    for item in sorted(root_path.rglob("*")):
        if item.is_file():
            yield item


def compute_relative_path(root: str | Path, file_path: str | Path) -> Path:
    """
    Compute a safe relative path from a directory root.
    """
    normalized_root = normalize_path(root)
    normalized_file = normalize_path(file_path)

    relative_path = normalized_file.relative_to(normalized_root)

    if relative_path.is_absolute():
        raise ValueError("Relative path must not be absolute.")

    if any(part == ".." for part in relative_path.parts):
        raise ValueError("Relative path must not contain parent traversal.")

    return relative_path


def build_transfer_manifest(
    sources: Iterable[str | Path],
) -> tuple[list[TransferFile], int]:
    """
    Build a flat transfer manifest from one or multiple sources.

    Supported sources:
    - file
    - directory
    - list of files and/or directories

    Returns:
        (items, total_size_bytes)
    """
    files: list[TransferFile] = []
    total_size = 0

    for source in sources:
        source_path = normalize_path(source)

        if not source_path.exists():
            raise FileNotFoundError(source_path)

        if source_path.is_file():
            size = source_path.stat().st_size
            checksum = compute_file_checksum(source_path)

            item = TransferFile(
                path=source_path,
                relative_path=Path(source_path.name),
                item_type=TransferItemType.FILE,
                size_bytes=size,
                checksum=checksum,
            )

            files.append(item)
            total_size += size
            continue

        if source_path.is_dir():
            for file_path in walk_directory(source_path):
                size = file_path.stat().st_size
                checksum = compute_file_checksum(file_path)
                relative_path = compute_relative_path(source_path, file_path)

                item = TransferFile(
                    path=file_path,
                    relative_path=relative_path,
                    item_type=TransferItemType.FILE,
                    size_bytes=size,
                    checksum=checksum,
                )

                files.append(item)
                total_size += size
            continue

        raise FileNotFoundError(source_path)

    return files, total_size


def compute_total_size(files: Iterable[TransferFile]) -> int:
    """
    Compute the total size in bytes for file items only.
    """
    total = 0

    for item in files:
        if item.is_file:
            total += item.size_bytes

    return total