
"""`cs2kit play` is what the launcher app runs, so its refusals are the app's UX."""
import argparse
import json
from pathlib import Path

import pytest

from cs2kit import integrity, play, probe
from cs2kit.util import EXIT_INTEGRITY, EXIT_NOT_READY, EXIT_OK


def args(**kw):
    base = {"prefix": None, "profile": None, "print_only": True, "force": False,
            "start_steam_anyway": False, "json": False, "extra": []}
    base.update(kw)
    return argparse.Namespace(**base)


def make_bottle(sandbox, with_steam=True):
    (sandbox.prefix / "system.reg").write_text("WINE REGISTRY")
    if with_steam:
        steam = sandbox.prefix / "drive_c" / "Program Files (x86)" / "Steam"
        steam.mkdir(parents=True, exist_ok=True)
        (steam / "Steam.exe").write_bytes(b"MZ")


def test_diagnose_names_the_next_action_at_every_stage(sandbox, monkeypatch):
    monkeypatch.setattr(play, "steam_running", lambda: True)
    assert "cs2kit setup" in play.diagnose(sandbox.prefix)          # no bottle

    make_bottle(sandbox, with_steam=False)
    assert "Steam client is not installed" in play.diagnose(sandbox.prefix)

    make_bottle(sandbox)
    msg = play.diagnose(sandbox.prefix)
    assert "not installed in the bottle" in msg and "install CS2" in msg


def test_a_healthy_bottle_diagnoses_clean(sandbox, cs2_tree, monkeypatch):
    make_bottle(sandbox)
    assert play.diagnose(sandbox.prefix) is None


def test_play_refuses_a_modified_game(sandbox, cs2_tree, monkeypatch, capsys):
    make_bottle(sandbox)
    integrity.create_baseline()
    (cs2_tree / "client.dll").write_bytes(b"MZ-tampered")
    assert play.cmd_play(args(json=True)) == EXIT_INTEGRITY
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False and "Verify integrity" in payload["detail"]


def test_play_without_a_game_explains_instead_of_crashing(sandbox, monkeypatch, capsys):
    make_bottle(sandbox)
    monkeypatch.setattr(play, "steam_running", lambda: True)
    assert play.cmd_play(args(json=True)) == EXIT_NOT_READY
    assert "install CS2" in json.loads(capsys.readouterr().out)["detail"]


def test_the_plan_is_resolved_from_disk_not_baked(sandbox, cs2_tree, monkeypatch):
    make_bottle(sandbox)
    monkeypatch.setattr(play, "steam_running", lambda: True)
    plan = play.build(sandbox.prefix)
    assert plan["cs2_exe"] == str(cs2_tree / "cs2.exe")
    assert plan["env"]["WINEMSYNC"] == "1"
    assert "-vulkan" not in plan["options"]


def test_play_never_accepts_vulkan(sandbox, cs2_tree):
    make_bottle(sandbox)
    with pytest.raises(Exception) as exc:
        play.build(sandbox.prefix, extra=["-vulkan"])
    assert "-vulkan" in str(exc.value)


def test_the_game_is_found_in_a_bottle_only_library(sandbox, tmp_path, monkeypatch):
    """After `bottle migrate` the game is no longer under the macOS Steam root."""
    lib = tmp_path / "cs2-library" / "steamapps" / "common" / "Counter-Strike Global Offensive"
    win64 = lib / "game" / "bin" / "win64"
    win64.mkdir(parents=True)
    (win64 / "cs2.exe").write_bytes(b"MZ")
    (tmp_path / "cs2-library" / "steamapps" / "appmanifest_730.acf").write_text(
        '"AppState" { "installdir" "Counter-Strike Global Offensive" "buildid" "1" }')
    assert probe.cs2_exe() == win64 / "cs2.exe"
