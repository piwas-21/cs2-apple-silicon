
"""`cs2kit setup` is the command a new user runs first, so its plan and its
blocking checks are contract, not convenience."""
import argparse
import json

import pytest

from cs2kit import engine, setup
from cs2kit.util import EXIT_NOT_READY, EXIT_OK


def args(**kw):
    base = {"engine": engine.RECOMMENDED, "prefix": None, "profile": "balanced-1080p",
            "app_dest": "/tmp/x.app", "dry_run": True, "json": False}
    base.update(kw)
    return argparse.Namespace(**base)


def test_the_plan_names_every_step_a_user_would_otherwise_do_by_hand():
    steps = " | ".join(setup.plan(args())).lower()
    for needed in ("wine engine", "dxmt", "bottle", "steam client", "library", "launcher"):
        assert needed in steps, f"setup does not mention {needed}"


def test_dry_run_changes_nothing_and_succeeds(capsys, sandbox):
    assert setup.cmd_setup(args(dry_run=True)) == EXIT_OK
    out = capsys.readouterr().out
    assert "dry run" in out and "1." in out


def test_preflight_blocks_on_the_things_that_cannot_be_worked_around(monkeypatch, sandbox):
    monkeypatch.setattr(setup.probe, "snapshot", lambda *a, **k: {
        "stable": {"arch": "x86_64"},
        "volatile": {"rosetta": False, "free_gib": 3}})
    problems = " | ".join(setup.preflight())
    assert "Apple Silicon" in problems
    assert "Rosetta" in problems and "softwareupdate" in problems
    assert "GiB free" in problems

    monkeypatch.setattr(setup.probe, "snapshot", lambda *a, **k: {
        "stable": {"arch": "arm64"},
        "volatile": {"rosetta": True, "free_gib": 200}})
    assert setup.preflight() == []


def test_setup_refuses_to_start_when_blocked(monkeypatch, sandbox, capsys):
    monkeypatch.setattr(setup.probe, "snapshot", lambda *a, **k: {
        "stable": {"arch": "arm64"},
        "volatile": {"rosetta": False, "free_gib": 200}})
    assert setup.cmd_setup(args(dry_run=False)) == EXIT_NOT_READY
    assert "blocked:" in capsys.readouterr().out


def test_dxmt_release_is_pinned_and_checksummed():
    assert setup.DXMT_RELEASE["sha256"] and len(setup.DXMT_RELEASE["sha256"]) == 64
    assert setup.DXMT_RELEASE["version"] in setup.DXMT_RELEASE["url"]


def test_steam_setup_is_pinned():
    # The one artifact whose digest can legitimately drift (Valve reissues it),
    # and therefore the one that must never silently run unverified.
    assert setup.STEAM_SETUP["sha256"] and len(setup.STEAM_SETUP["sha256"]) == 64


class _FakeDownload:
    """Stands in for engine.download: writes a file and enforces the pin as the real one does."""

    def __init__(self, digest):
        self.digest = digest
        self.pins_seen = []

    def __call__(self, url, dest, sha256=None, progress=None):
        self.pins_seen.append(sha256)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"MZ installer")
        if sha256 and self.digest != sha256:
            dest.unlink()
            raise engine.EngineError(
                f"{dest.name}: sha256 {self.digest} does not match the recorded {sha256}")
        return dest


def test_steam_installer_refuses_a_digest_outside_the_pin(monkeypatch, tmp_path):
    monkeypatch.setenv("CS2KIT_SETUP_HOME", str(tmp_path))
    fake = _FakeDownload("0" * 64)
    monkeypatch.setattr(setup.engine, "download", fake)
    with pytest.raises(setup.SetupError, match="--trust-steam-sha"):
        setup.fetch_steam_installer(log=lambda m: None)
    assert not (tmp_path / "downloads" / "SteamSetup.exe").exists()   # nothing left to run later


def test_steam_installer_trust_flag_accepts_the_new_file(monkeypatch, tmp_path):
    monkeypatch.setenv("CS2KIT_SETUP_HOME", str(tmp_path))
    fake = _FakeDownload("0" * 64)
    monkeypatch.setattr(setup.engine, "download", fake)
    installer = setup.fetch_steam_installer(log=lambda m: None, trust_unpinned=True)
    assert installer.read_bytes() == b"MZ installer"
    # the second download must be genuinely unpinned, not a re-check of the stale pin
    assert fake.pins_seen == [setup.STEAM_SETUP["sha256"], None]


def test_steam_installer_downloads_once_when_the_pin_matches(monkeypatch, tmp_path):
    monkeypatch.setenv("CS2KIT_SETUP_HOME", str(tmp_path))
    fake = _FakeDownload(setup.STEAM_SETUP["sha256"])
    monkeypatch.setattr(setup.engine, "download", fake)
    assert setup.fetch_steam_installer(log=lambda m: None).name == "SteamSetup.exe"
    assert fake.pins_seen == [setup.STEAM_SETUP["sha256"]]


def test_wine_env_always_carries_msync(tmp_path):
    env = setup.wine_env(tmp_path / "prefix", tmp_path / "wine")
    # A wineserver started without this poisons the prefix for every later process.
    assert env["WINEMSYNC"] == "1"
    assert env["WINEPREFIX"].endswith("prefix")
    assert str(tmp_path / "wine" / "bin") in env["PATH"]
    assert env["DYLD_FALLBACK_LIBRARY_PATH"].endswith("lib")


def test_install_dxmt_reuses_an_existing_unpack(monkeypatch, tmp_path):
    monkeypatch.setenv("CS2KIT_SETUP_HOME", str(tmp_path))
    unpacked = tmp_path / "dxmt" / "v0.80" / "x86_64-unix"
    unpacked.mkdir(parents=True)
    (unpacked / "winemetal.so").write_bytes(b"so")

    def fail(*a, **k):
        raise AssertionError("setup re-downloaded DXMT it already had")

    monkeypatch.setattr(engine, "download", fail)
    assert setup.install_dxmt(log=lambda m: None) == unpacked.parent
