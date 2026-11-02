"""Extraction attacks must be rejected identically on Python 3.9 and newer."""
import io
import tarfile

import pytest

from cs2kit import archive as archive_mod, engine


def make_tar(path, entries):
    with tarfile.open(path, "w") as tar:
        for name, kind, value in entries:
            item = tarfile.TarInfo(name)
            if kind == "file":
                data = value.encode()
                item.size = len(data)
                item.mode = 0o6755
                tar.addfile(item, io.BytesIO(data))
            else:
                item.type = {"symlink": tarfile.SYMTYPE, "hardlink": tarfile.LNKTYPE,
                             "fifo": tarfile.FIFOTYPE, "dir": tarfile.DIRTYPE}[kind]
                item.linkname = value
                tar.addfile(item)
    return path


@pytest.mark.parametrize("entries", [
    [("../outside", "file", "changed")],
    [("/absolute", "file", "changed")],
    [("C:/absolute", "file", "changed")],
    [("pkg\\..\\outside", "file", "changed")],
    [("pipe", "fifo", "")],
    [("pkg/link", "hardlink", "../outside"), ("pkg/link", "file", "changed")],
    [("pkg/link", "hardlink", "../outside")],
    [("sub", "symlink", "."), ("a", "symlink", "sub/..")],
    [("a", "symlink", "b"), ("b", "symlink", "a")],
    [("a", "hardlink", "b"), ("b", "hardlink", "a")],
    [("a", "symlink", "../outside")],
    [("same", "file", "one"), ("same", "file", "two")],
    [("a", "symlink", "."), ("a/outside", "file", "changed")],
])
def test_malicious_archive_leaves_destination_and_outside_unchanged(tmp_path, entries):
    outside = tmp_path / "outside"
    outside.write_text("original")
    dest = tmp_path / "out"
    archive = make_tar(tmp_path / "attack.tar", [("good", "file", "ok"), *entries])
    with pytest.raises(engine.EngineError):
        engine.extract(archive, dest)
    assert outside.read_text() == "original"
    assert not dest.exists()


@pytest.mark.parametrize("leaf", [False, True])
def test_existing_destination_symlink_cannot_redirect_writes(tmp_path, leaf):
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "file"
    sentinel.write_text("original")
    dest = tmp_path / "out"
    dest.mkdir()
    if leaf:
        (dest / "pkg").mkdir()
        (dest / "pkg" / "file").symlink_to(sentinel)
    else:
        (dest / "pkg").symlink_to(outside, target_is_directory=True)
    archive = make_tar(tmp_path / "attack.tar", [("pkg/file", "file", "changed")])
    with pytest.raises(engine.EngineError):
        engine.extract(archive, dest)
    assert sentinel.read_text() == "original"


def test_real_framework_links_hardlinks_and_repeat_extraction(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("tar extraction APIs must not be used, even on old interpreters")

    monkeypatch.setattr(tarfile.TarFile, "extractall", forbidden)
    monkeypatch.setattr(tarfile.TarFile, "extract", forbidden)
    archive = make_tar(tmp_path / "framework.tar", [
        ("Pkg/Versions/1/share/font", "file", "font"),
        ("Pkg/Versions/1/etc/fonts/conf.d/link", "symlink", "../../../share/font"),
        ("Pkg/Versions/Current", "symlink", "1"),
        ("Pkg/Resources", "symlink", "Versions/Current/share"),
        ("Pkg/copy", "hardlink", "Pkg/Versions/1/share/font"),
    ])
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "unrelated").write_text("keep")
    for _ in range(2):
        engine.extract(archive, dest)
        assert (dest / "Pkg/Resources/font").read_text() == "font"
        assert (dest / "Pkg/copy").read_text() == "font"
        assert (dest / "unrelated").read_text() == "keep"
        assert (dest / "Pkg/copy").stat().st_mode & 0o6000 == 0


def test_destination_root_symlink_is_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    dest = tmp_path / "out"
    dest.symlink_to(outside, target_is_directory=True)
    archive = make_tar(tmp_path / "attack.tar", [("file", "file", "changed")])
    with pytest.raises(engine.EngineError):
        engine.extract(archive, dest)
    assert not list(outside.iterdir())


@pytest.mark.parametrize("limit", ["MAX_BYTES", "MAX_FILE_BYTES", "MAX_MEMBERS"])
def test_expansion_limits_are_enforced(tmp_path, monkeypatch, limit):
    monkeypatch.setattr(archive_mod, limit, 1)
    archive = make_tar(tmp_path / "large.tar", [("one", "file", "data"), ("two", "file", "data")])
    with pytest.raises(engine.EngineError):
        engine.extract(archive, tmp_path / "out")


def test_directory_swap_during_publication_cannot_write_outside(tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "file").write_text("original")
    dest = tmp_path / "out"
    (dest / "pkg").mkdir(parents=True)
    original = archive_mod._check_existing

    def swap(*args):
        original(*args)
        (dest / "pkg").rmdir()
        (dest / "pkg").symlink_to(outside, target_is_directory=True)

    monkeypatch.setattr(archive_mod, "_check_existing", swap)
    archive = make_tar(tmp_path / "swap.tar", [("pkg/file", "file", "changed")])
    with pytest.raises(engine.EngineError):
        engine.extract(archive, dest)
    assert (outside / "file").read_text() == "original"
