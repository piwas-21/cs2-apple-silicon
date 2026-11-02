"""T-004: unpack downloads without trusting archive paths or filesystem links.

All interpreters use the same policy, including macOS Python 3.9 without tar
filters. Materialize in a private directory first; never use tar.extract().
Publish through directory descriptors so replacing a destination symlink cannot
redirect a write. Existing unrelated files are retained.
"""
from __future__ import annotations

import os
import re
import shutil
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Dict, Iterator, List

MAX_MEMBERS = 200_000
MAX_BYTES = 20 * 1024 ** 3
MAX_FILE_BYTES = 4 * 1024 ** 3


class UnsafeArchive(ValueError):
    pass


def _name(value: str) -> str:
    path = PurePosixPath(value)
    if (not value or len(value) > 4096 or "\0" in value or path.is_absolute() or ".." in path.parts or "\\" in value
            or re.match(r"^[A-Za-z]:", value)):
        raise UnsafeArchive(f"unsafe archive path: {value!r}")
    return str(path)


def _members(tar: tarfile.TarFile) -> Dict[str, tarfile.TarInfo]:
    members: Dict[str, tarfile.TarInfo] = {}
    total = 0
    for count, member in enumerate(tar, 1):
        if count > MAX_MEMBERS:
            raise UnsafeArchive("archive has too many members")
        name = _name(member.name)
        if name == "." and member.isdir():
            continue
        if name == "." or not (member.isdir() or member.isfile() or member.issym() or member.islnk()):
            raise UnsafeArchive(f"unsupported archive member: {member.name!r}")
        previous = members.get(name)
        if previous and not (previous.isdir() and member.isdir()):
            raise UnsafeArchive(f"duplicate archive member: {name}")
        if member.size < 0 or member.size > MAX_FILE_BYTES:
            raise UnsafeArchive(f"archive member is too large: {name}")
        total += member.size
        if total > MAX_BYTES:
            raise UnsafeArchive("archive exceeds the expanded size limit")
        members[name] = member
    for name in members:
        for parent in PurePosixPath(name).parents:
            ancestor = members.get(str(parent))
            if ancestor and not ancestor.isdir():
                raise UnsafeArchive(f"archive writes through a non-directory: {name}")
    return members


def _inside(root: Path, candidate: Path) -> Path:
    try:
        try:
            # Python 3.13 no longer raises for cycles with strict=False.
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError:
            resolved = candidate.resolve(strict=False)
        resolved.relative_to(root)
    except (ValueError, RuntimeError, OSError) as exc:
        raise UnsafeArchive(f"link escapes the archive or contains a cycle: {candidate}") from exc
    return resolved


def _materialize(tar: tarfile.TarFile, stage: Path,
                 members: Dict[str, tarfile.TarInfo]) -> None:
    for name, member in members.items():
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if member.isdir():
            target.mkdir(exist_ok=True)
        elif member.isfile():
            source = tar.extractfile(member)
            if source is None:
                raise UnsafeArchive(f"missing archive data: {name}")
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
            target.chmod(member.mode & 0o755)
    # Relative framework symlinks are necessary. Validate the complete graph
    # after creating every link, before copying any hard link or publishing.
    for name, member in members.items():
        if member.issym():
            if (not member.linkname or len(member.linkname) > 4096 or "\0" in member.linkname
                    or PurePosixPath(member.linkname).is_absolute() or "\\" in member.linkname):
                raise UnsafeArchive(f"unsafe symbolic link: {name}")
            (stage / name).symlink_to(member.linkname)
    for name, member in members.items():
        if member.issym():
            _inside(stage, stage / name)
    pending = {name: member for name, member in members.items() if member.islnk()}
    total_bytes = sum(m.size for m in members.values())
    copied_bytes = 0
    passes = 0
    while pending:
        passes += 1
        if passes > 64:
            raise UnsafeArchive("archive hard-link chain is too deep")
        progressed: List[str] = []
        for name, member in pending.items():
            # Hard links are rooted at the archive, unlike symbolic links.
            source = _inside(stage, stage / _name(member.linkname))
            if source.is_file():
                copied_bytes += source.stat().st_size
                if copied_bytes + total_bytes > MAX_BYTES:
                    raise UnsafeArchive("hard links exceed the expanded size limit")
                shutil.copyfile(source, stage / name)
                (stage / name).chmod(member.mode & 0o755)
                progressed.append(name)
        if not progressed:
            raise UnsafeArchive("archive has unresolved or cyclic hard links")
        for name in progressed:
            del pending[name]


@contextmanager
def _directory(root_fd: int, parts: tuple, create: bool = False) -> Iterator[int]:
    fd = os.dup(root_fd)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, 0o755, dir_fd=fd)
                except FileExistsError:
                    pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _check_existing(dest: Path, members: Dict[str, tarfile.TarInfo]) -> None:
    for name, member in members.items():
        parts = PurePosixPath(name).parts
        for index in range(len(parts)):
            path = dest.joinpath(*parts[:index + 1])
            if path.is_symlink():
                # Replacing the exact symlink leaf is safe; never traverse it.
                if index != len(parts) - 1 or not member.issym():
                    raise UnsafeArchive(f"destination contains a symbolic link: {path}")
            elif path.exists():
                expected_dir = index < len(parts) - 1 or member.isdir()
                if path.is_dir() != expected_dir or (not expected_dir and not path.is_file()):
                    raise UnsafeArchive(f"destination has a conflicting file type: {path}")


def _publish(stage: Path, dest: Path, members: Dict[str, tarfile.TarInfo]) -> None:
    # Resolve the archive's graph first, then check the corresponding target
    # in the destination. A legitimate dangling wrapper link must not bind to
    # an unrelated retained symlink that redirects it outside the chosen root.
    for name, member in members.items():
        if member.issym():
            relative = _inside(stage, stage / name).relative_to(stage)
            _inside(dest, dest / relative)
    _check_existing(dest, members)
    dest.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(dest), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for name, member in members.items():
            parts = PurePosixPath(name).parts
            with _directory(fd, parts[:-1], create=True) as parent:
                if member.isdir():
                    with _directory(parent, (parts[-1],), create=True):
                        pass
                else:
                    # replace() never follows a leaf symlink. Directory handles
                    # ensure a changed ancestor cannot redirect publication.
                    os.replace(str(stage / name), parts[-1], dst_dir_fd=parent)
    finally:
        os.close(fd)


def unpack(archive: Path, dest: Path) -> Path:
    dest = Path(dest)
    if dest.is_symlink():
        raise UnsafeArchive(f"destination is a symbolic link: {dest}")
    # Resolve parent aliases such as macOS /tmp -> /private/tmp once, then bind
    # publication to directory descriptors below this chosen destination.
    actual = dest.parent.resolve() / dest.name
    actual.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix=".cs2kit-extract-", dir=str(actual.parent)) as temporary:
            stage = Path(temporary).resolve()
            with tarfile.open(archive) as tar:
                members = _members(tar)
                _materialize(tar, stage, members)
            _publish(stage, actual, members)
    except (tarfile.TarError, OSError) as exc:
        raise UnsafeArchive(f"cannot safely unpack {archive}: {exc}") from exc
    return dest
