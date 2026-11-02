"""T-025/T-027: execute generated scripts against harmless temporary payloads."""
import os
import hashlib
import plistlib
import subprocess

import pytest

from cs2kit import app, config, engine, recipe, setup


@pytest.mark.parametrize("existing", [None, "", "already set ' $(false)"])
def test_env_script_round_trips_prefix_and_payload_values(sandbox, monkeypatch, existing):
    marker = sandbox.root / "marker"
    prefix = str(sandbox.root / f"a b'$(touch {marker})")
    monkeypatch.setenv("WINEPREFIX", prefix)
    rec = recipe.Recipe("safe", {"schema": 1, "kind": "profile", "name": "safe",
        "provenance": "test", "env": {"WINEDEBUG": f"'\"; $(touch {marker})"},
        "game": {"launch_options": [f"$(touch {marker})", "a b"]}})
    script = config.render_env_script(rec)
    env = dict(os.environ)
    env.pop("WINEPREFIX", None)
    if existing is not None:
        env["WINEPREFIX"] = existing
    proc = subprocess.run(["bash", "-c", script +
        '\nprintf "%s\\0" "$WINEPREFIX" "$WINEDEBUG" "$CS2KIT_LAUNCH_OPTIONS"'],
        capture_output=True, env=env, timeout=10)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.decode().split("\0")[:-1] == [existing or prefix, rec.env["WINEDEBUG"],
                                                     " ".join(rec.launch_options)]
    assert not marker.exists()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "safe\necho injected", ".", "bad name"])
def test_profile_names_cannot_escape_state_or_inject_script_lines(sandbox, name):
    with pytest.raises(recipe.RecipeError):
        config.env_script_path(name)


@pytest.mark.parametrize("key", ["bad; command", "é", "1BAD", "A\nB"])
def test_env_keys_are_ascii_shell_identifiers(sandbox, key):
    rec = recipe.Recipe("safe", {"schema": 1, "kind": "profile", "name": "safe",
                                   "provenance": "test", "env": {key: "1"}})
    with pytest.raises(recipe.RecipeError):
        config.render_env_script(rec)


def test_shader_cache_home_is_expanded_before_shell_quoting(sandbox, monkeypatch):
    monkeypatch.setenv("HOME", str(sandbox.root / "home with space"))
    rec = recipe.resolve("balanced-1080p")
    proc = subprocess.run(["bash", "-c", config.render_env_script(rec) + '\nprintf "%s" "$DXMT_SHADER_CACHE"'],
                          capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0
    assert proc.stdout == os.path.expandvars(rec.env["DXMT_SHADER_CACHE"])


def test_launcher_shell_and_plist_round_trip_hostile_values(sandbox, monkeypatch):
    root = sandbox.root / "checkout ' with spaces"
    (root / "bin").mkdir(parents=True)
    marker = sandbox.root / "marker"
    record = sandbox.root / "arguments"
    target = root / "bin/cs2kit"
    target.write_text('#!/bin/bash\nprintf "%s\\0" "$@" > "$RECORD"\n')
    target.chmod(0o755)
    monkeypatch.setenv("CS2KIT_REPO", str(root))
    monkeypatch.setenv("HOME", str(sandbox.root))
    monkeypatch.setenv("RECORD", str(record))
    profile = f'x"; touch {marker} #'
    dest = sandbox.root / "A&B.app"
    app._write_script_app(dest, sandbox.prefix, profile, "A&B <Test>")
    proc = subprocess.run(["bash", str(dest / "Contents/MacOS/cs2kit-launch")], timeout=10)
    assert proc.returncode == 0
    assert record.read_bytes().decode().split("\0")[:-1] == ["play", "--profile", profile, "--gui", "--detach"]
    assert not marker.exists()
    with (dest / "Contents/Info.plist").open("rb") as file:
        assert plistlib.load(file)["CFBundleName"] == "A&B <Test>"


def test_every_executable_download_has_a_recorded_checksum():
    assert engine.DYLIB_BUNDLE["sha256"]
    assert setup.STEAM_SETUP["sha256"]
    assert setup.DXMT_RELEASE["sha256"]
    assert all(entry.sha256 for entry in engine.ENGINES.values())


@pytest.mark.parametrize("key", ["BASH_ENV", "PATH", "PYTHONPATH", "DYLD_INSERT_LIBRARIES", "LD_PRELOAD"])
def test_profiles_cannot_inject_process_loader_or_shell_environment(sandbox, key):
    rec = recipe.Recipe("safe", {"schema": 1, "name": "safe", "kind": "profile",
                                  "provenance": "test", "env": {key: "/tmp/payload"}})
    with pytest.raises(recipe.RecipeError):
        rec.require_valid()


def test_download_refuses_bad_bytes_before_publishing(sandbox, monkeypatch):
    dest = sandbox.root / "installer.exe"
    monkeypatch.setattr(engine, "_fetch", lambda url, path, progress: path.write_bytes(b"wrong"))
    with pytest.raises(engine.EngineError):
        engine.download("https://example.invalid/installer", dest, "0" * 64)
    assert not dest.exists()
    assert not list(sandbox.root.glob(".download-*"))


def test_download_never_follows_a_destination_symlink(sandbox):
    outside = sandbox.root / "retained"
    outside.write_bytes(b"keep")
    dest = sandbox.root / "installer.exe"
    dest.symlink_to(outside)
    with pytest.raises(engine.EngineError):
        engine.download("https://example.invalid/installer", dest, "0" * 64)
    assert outside.read_bytes() == b"keep"


@pytest.mark.parametrize("url", ["http://example.invalid/file", "file:///tmp/file"])
def test_download_rejects_non_https_before_network_access(sandbox, url):
    with pytest.raises(engine.EngineError, match="HTTPS"):
        engine._fetch(url, sandbox.root / "file")


def test_redirect_handler_rejects_downgrades_before_following(sandbox):
    with pytest.raises(engine.EngineError, match="HTTPS"):
        engine._HTTPSRedirect().redirect_request(None, None, 302, "", {}, "http://example.invalid/file")


def test_steam_pin_failure_never_executes_the_installer(sandbox, monkeypatch):
    monkeypatch.setenv("CS2KIT_SETUP_HOME", str(sandbox.root))
    installer = sandbox.root / "downloads/SteamSetup.exe"
    installer.parent.mkdir()
    installer.write_bytes(b"untrusted")
    monkeypatch.setattr(setup, "run", lambda *a, **kw: pytest.fail("mismatched bytes were executed"))
    with pytest.raises(engine.EngineError):
        setup.install_steam_client(sandbox.prefix, sandbox.root / "wine", log=lambda m: None)
    assert not installer.exists()


def test_explicit_steam_digest_verifies_the_same_file_before_execution(sandbox, monkeypatch):
    monkeypatch.setenv("CS2KIT_SETUP_HOME", str(sandbox.root))
    installer = sandbox.root / "downloads/SteamSetup.exe"
    installer.parent.mkdir()
    installer.write_bytes(b"verified newer installer")
    expected = hashlib.sha256(installer.read_bytes()).hexdigest()
    calls = []

    def fake_run(cmd, **kwargs):
        assert installer.read_bytes() == b"verified newer installer"
        calls.append(cmd)
        client = sandbox.prefix / "drive_c/Program Files (x86)/Steam/Steam.exe"
        client.parent.mkdir(parents=True)
        client.write_bytes(b"client")

    monkeypatch.setattr(setup, "run", fake_run)
    setup.install_steam_client(sandbox.prefix, sandbox.root / "wine", log=lambda m: None,
                               installer_sha256=expected)
    assert len(calls) == 1 and calls[0][1] == str(installer)


def test_invalid_explicit_steam_digest_cannot_disable_verification(sandbox):
    with pytest.raises(setup.SetupError):
        setup.install_steam_client(sandbox.prefix, sandbox.root / "wine", log=lambda m: None,
                                   installer_sha256="trust-me")


def test_steam_start_uses_an_argument_array_and_no_shell(sandbox, monkeypatch):
    from cs2kit import play

    client = sandbox.prefix / "Steam with spaces/Steam.exe"
    client.parent.mkdir()
    client.write_bytes(b"client")
    monkeypatch.setenv("HOME", str(sandbox.root))
    monkeypatch.setattr(play.bottle, "wine_root", lambda: sandbox.root / "wine")
    monkeypatch.setattr(play, "steam_running", lambda: True)
    monkeypatch.setattr(play.time, "sleep", lambda seconds: None)
    calls = []
    monkeypatch.setattr(play.subprocess, "Popen", lambda cmd, **kw: calls.append((cmd, kw)))
    play._start_steam(sandbox.prefix, client)
    assert calls[0][0] == [str(sandbox.root / "wine/bin/wine"), str(client), "-no-cef-sandbox"]
    assert calls[0][1]["cwd"] == str(client.parent)
    assert not calls[0][1].get("shell")


def test_file_derived_identifiers_cannot_escape_state(sandbox):
    from cs2kit import bench, integrity

    with pytest.raises(integrity.IntegrityError):
        integrity.baseline_path("../../outside")
    with pytest.raises(bench.BenchError):
        bench.session_dir("../../outside")
    with pytest.raises(bench.BenchError):
        bench.save_session({"env_id": "safe", "id": "../../outside"})
    assert not (sandbox.root / "outside.json").exists()


def test_json_write_does_not_follow_a_leaf_symlink(sandbox):
    from cs2kit.util import write_json

    outside = sandbox.root / "retained"
    outside.write_text("original")
    target = sandbox.home / "state.json"
    target.symlink_to(outside)
    with pytest.raises(ValueError):
        write_json(target, {"changed": True})
    assert outside.read_text() == "original"
