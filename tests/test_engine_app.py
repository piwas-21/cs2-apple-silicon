
"""Tests for the two commands that remove manual steps: engine and app."""
import argparse
import json
import stat
import tarfile
from pathlib import Path

import pytest

from cs2kit import app as app_mod, engine
from cs2kit.util import EXIT_NOT_READY, EXIT_OK


def make_engine_archive(tmp_path, name="WS12WineFake.tar.xz"):
    root = tmp_path / "src" / "wswine.bundle"
    (root / "bin").mkdir(parents=True)
    (root / "lib" / "wine" / "x86_64-unix").mkdir(parents=True)
    (root / "bin" / "wine").write_text("#!/bin/sh\n")
    archive = tmp_path / name
    with tarfile.open(archive, "w:xz") as tar:
        tar.add(root, arcname="wswine.bundle")
    return archive


def test_engine_registry_states_which_build_works_and_why():
    assert engine.RECOMMENDED == "sikarugir-10"
    rec = engine.ENGINES[engine.RECOMMENDED]
    assert rec.verdict == "recommended" and rec.needs_dylibs
    # The two we measured as unusable must stay listed, with the reason.
    assert engine.ENGINES["gcenx-11"].verdict == "broken"
    assert "metal view" in engine.ENGINES["gcenx-11"].why
    assert engine.ENGINES["crossover-24"].verdict == "broken"
    assert "0x3008" in engine.ENGINES["crossover-24"].why


def test_checksum_mismatch_deletes_the_download(tmp_path):
    blob = tmp_path / "thing.tar.xz"
    blob.write_bytes(b"not the real archive")
    with pytest.raises(engine.EngineError) as exc:
        engine.download("file:///unused", blob, sha256="0" * 64)
    assert "sha256" in str(exc.value)
    assert not blob.exists(), "a mismatched archive must not be left on disk"


def test_extract_and_find_bundle(tmp_path):
    archive = make_engine_archive(tmp_path)
    dest = tmp_path / "out"
    engine.extract(archive, dest)
    bundle = engine.find_bundle(dest, engine.ENGINES["sikarugir-10"])
    assert bundle is not None and (bundle / "bin" / "wine").is_file()


def test_stage_dylibs_is_required_and_idempotent(tmp_path):
    archive = make_engine_archive(tmp_path)
    dest = tmp_path / "out"
    engine.extract(archive, dest)
    bundle = engine.find_bundle(dest, engine.ENGINES["sikarugir-10"])
    frameworks = tmp_path / "fw"
    frameworks.mkdir()
    with pytest.raises(engine.EngineError):
        engine.stage_dylibs(bundle, frameworks)          # nothing to stage is an error
    (frameworks / "libinotify.0.dylib").write_bytes(b"x")
    (frameworks / "libgnutls.30.dylib").write_bytes(b"y")
    staged = engine.stage_dylibs(bundle, frameworks)
    assert sorted(staged) == ["libgnutls.30.dylib", "libinotify.0.dylib"]
    assert (bundle / "lib" / "libinotify.0.dylib").is_file()
    assert engine.stage_dylibs(bundle, frameworks) == staged   # idempotent


def test_app_bundle_is_double_clickable_and_guarded(sandbox, tmp_path, cs2_tree):
    wine_root = tmp_path / "wine"
    (wine_root / "bin").mkdir(parents=True)
    dest = tmp_path / "CS2.app"
    result = app_mod.build_app(dest, wine_root, prefix=sandbox.prefix, profile="balanced-1080p")

    launcher = Path(result["launcher"])
    assert launcher.exists() and launcher.stat().st_mode & stat.S_IXUSR, "must be executable"
    body = launcher.read_text()
    assert body.startswith("#!/bin/bash")
    assert "verify check" in body, "T-021: the app must refuse to launch a modified game"
    assert "-no-cef-sandbox" in body, "the Steam client needs it or it dies with 0x3008"
    assert str(sandbox.prefix) in body and str(wine_root) in body
    assert 'export WINEMSYNC="1"' in body
    assert "exec wine cs2.exe -novid -nojoy -console" in body

    plist = (dest / "Contents" / "Info.plist").read_text()
    assert "<key>CFBundleExecutable</key><string>cs2kit-launch</string>" in plist
    assert "org.cs2kit.cs2" in plist
    assert (dest / "Contents" / "PkgInfo").read_text() == "APPL????"


def test_app_points_at_the_real_game_directory(sandbox, cs2_tree, tmp_path):
    wine_root = tmp_path / "wine"
    (wine_root / "bin").mkdir(parents=True)
    result = app_mod.build_app(tmp_path / "X.app", wine_root, prefix=sandbox.prefix)
    assert result["game_dir"] == str(cs2_tree)


def test_app_create_without_wine_is_not_ready(sandbox, monkeypatch, tmp_path, capsys):
    from cs2kit import bottle

    monkeypatch.setattr(bottle, "which", lambda name: None)
    args = argparse.Namespace(dest=str(tmp_path / "Y.app"), wine_root=None, prefix=None,
                              game_dir=None, profile=None, name="Y", json=True)
    assert app_mod.cmd_create(args) == EXIT_NOT_READY
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False and "engine install" in payload["detail"]
