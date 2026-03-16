from __future__ import annotations

from pathlib import Path

from utils.file_utils import build_transfer_manifest


def test_manifest_single_file(tmp_path) -> None:
    file_path = tmp_path / "a.txt"
    file_path.write_text("hello", encoding="utf-8")

    files, total_size = build_transfer_manifest([file_path])

    assert len(files) == 1
    assert total_size == 5

    item = files[0]
    assert item.path == file_path.resolve()
    assert item.relative_path == Path("a.txt")
    assert item.size_bytes == 5
    assert item.checksum is not None
    assert len(item.checksum) == 64


def test_manifest_directory(tmp_path) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()

    file_a = folder / "a.txt"
    file_b = folder / "b.txt"

    file_a.write_text("abc", encoding="utf-8")
    file_b.write_text("def", encoding="utf-8")

    files, total_size = build_transfer_manifest([folder])

    assert len(files) == 2
    assert total_size == 6

    relative_paths = sorted(str(item.relative_path.as_posix()) for item in files)
    assert relative_paths == ["a.txt", "b.txt"]


def test_manifest_relative_paths(tmp_path) -> None:
    root = tmp_path / "root"
    sub = root / "sub"
    sub.mkdir(parents=True)

    file_path = sub / "file.txt"
    file_path.write_text("test", encoding="utf-8")

    files, total_size = build_transfer_manifest([root])

    assert len(files) == 1
    assert total_size == 4

    item = files[0]
    assert item.relative_path == Path("sub") / "file.txt"
    assert item.relative_path.as_posix() == "sub/file.txt"
    assert item.size_bytes == 4
    assert item.checksum is not None
    assert len(item.checksum) == 64