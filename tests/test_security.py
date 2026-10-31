"""Regression tests for the security hardening pass.

Covers: tar path-traversal refusal (engine.extract on Python < 3.12), sha256
pinning of the wrapper dylib bundle, and shell/AppleScript escaping of profile
values in generated scripts.
"""
import tarfile

import pytest

from cs2kit import app as app_mod
from cs2kit import config
from cs2kit import engine
from cs2kit import recipe as recipe_mod


def _write_tar(path, members):
    with tarfile.open(path, "x:xz") as tar:
        for name, content in members:
            data = content.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, __import__("io").BytesIO(data))


def _write_tar_with_link(path, files, link_name, link_target):
    with tarfile.open(path, "x:xz") as tar:
        for name, content in files:
            data = content.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, __import__("io").BytesIO(data))
        link = tarfile.TarInfo(link_name)
        link.type = tarfile.SYMTYPE
        link.linkname = link_target
        tar.addfile(link)


def test_extract_refuses_path_traversal(tmp_path):
    archive = tmp_path / "evil.tar.xz"
    _write_tar(archive, [("good.txt", "ok"),
                         ("../../escaped.txt", "pwned")])
    with pytest.raises(engine.EngineError):
        engine.extract(archive, tmp_path / "out")
    assert not (tmp_path / "escaped.txt").exists()


def test_extract_refuses_absolute_paths(tmp_path):
    archive = tmp_path / "evil2.tar.xz"
    _write_tar(archive, [("/etc/pwned.txt", "pwned")])
    with pytest.raises(engine.EngineError):
        engine.extract(archive, tmp_path / "out")


def test_extract_still_unpacks_clean_archives(tmp_path):
    archive = tmp_path / "ok.tar.xz"
    _write_tar(archive, [("bin/wine", "#!/bin/sh"), ("lib/x.so", "ELF")])
    out = engine.extract(archive, tmp_path / "out")
    assert (out / "bin" / "wine").read_text() == "#!/bin/sh"


def test_extract_allows_relative_links_that_stay_inside(tmp_path):
    # The shape that broke setup for real: GStreamer.framework inside the Wine
    # wrapper ships conf.d/*.conf -> ../../../share/fontconfig/conf.avail/*.conf.
    # The link climbs three levels and lands back inside the bundle - that is
    # legitimate and must extract (measured 2026-10-31, Template-1.0.11.tar.xz).
    archive = tmp_path / "framework.tar.xz"
    _write_tar_with_link(
        archive,
        [("Pkg.framework/Versions/1.0/share/fontconfig/conf.avail/65-nonlatin.conf", "font")],
        "Pkg.framework/Versions/1.0/etc/fonts/conf.d/65-nonlatin.conf",
        "../../../share/fontconfig/conf.avail/65-nonlatin.conf")
    out = engine.extract(archive, tmp_path / "out")
    link = out / "Pkg.framework" / "Versions" / "1.0" / "etc" / "fonts" / "conf.d" / "65-nonlatin.conf"
    assert link.is_symlink()
    assert link.resolve().read_text() == "font"


def test_extract_refuses_links_that_escape_dest_without_a_dotdot_prefix(tmp_path):
    # Same refusal as before, but now decided by *resolution*, not by whether
    # the target merely contains ".." - an absolute target is caught here too.
    archive = tmp_path / "escape.tar.xz"
    _write_tar_with_link(archive, [], "pkg/link", "../../../escaped.txt")
    with pytest.raises(engine.EngineError):
        engine.extract(archive, tmp_path / "out")
    assert not (tmp_path.parent / "escaped.txt").exists()


def test_dylib_bundle_is_checksum_pinned():
    assert engine.DYLIB_BUNDLE.get("sha256"), "wrapper dylibs are executed code - pin them"


def test_env_script_quotes_values(sandbox):
    rec = recipe_mod.loads(
        'schema: 1\nname: evil\nkind: profile\nprovenance: measured\n'
        'env:\n  WINEDEBUG: "x; touch /tmp/pwned"\n'
        'display:\n  width: 1920\n  height: 1080\n')
    rec.require_valid()
    result = config.apply(rec)
    script = open(result["record"]["env_script"]).read()
    # The semicolon payload must stay inside shlex single quotes: unquoted, a
    # plain `export WINEDEBUG="x; touch ..."` would execute on source.
    assert "export WINEDEBUG='x; touch /tmp/pwned'" in script
    assert 'export WINEDEBUG="x; touch /tmp/pwned"' not in script


def test_env_script_rejects_non_identifier_keys():
    rec = recipe_mod.loads(
        'schema: 1\nname: evil2\nkind: profile\nprovenance: measured\n'
        'env:\n  "FOO; rm -rf ~": "1"\n'
        'display:\n  width: 1920\n  height: 1080\n')
    with pytest.raises(recipe_mod.RecipeError):
        config.apply(rec)


def test_launcher_script_escapes_profile_name(tmp_path):
    profile = 'x"; touch /tmp/pwned #'
    kind = app_mod._write_script_app(tmp_path / "T.app", tmp_path / "prefix",
                                     profile, "T")
    assert kind == "script"
    body = (tmp_path / "T.app" / "Contents" / "MacOS" / "cs2kit-launch").read_text()
    assert 'touch /tmp/pwned' in body
    assert body.count("'") >= 2                   # the payload sits inside shlex quotes
