
"""`cs2kit play` is what the launcher app runs, so its refusals are the app's UX."""
import argparse
import json
from pathlib import Path

import pytest

from cs2kit import integrity, play, probe
from cs2kit.util import EXIT_INTEGRITY, EXIT_NOT_READY, EXIT_OK, PASS


def args(**kw):
    base = {"prefix": None, "profile": None, "print_only": True, "force": False,
            "direct": False, "detach": False, "gui": False,
            "start_steam_anyway": False, "steam_only": False, "json": False, "extra": []}
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


def test_steam_running_matches_the_process_name_not_the_command_line(monkeypatch):
    """`pgrep -f steam.exe` matches any shell whose command line mentions it -
    including our own. That made the launcher skip starting Steam entirely."""
    from cs2kit.util import Proc

    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return Proc(0, "4242", "") if "-ix" in cmd else Proc(0, "9999", "")

    monkeypatch.setattr(play, "run", fake_run)
    assert play.steam_running() is True
    assert "-ix" in seen["cmd"], "must match the exact process name"
    assert "-f" not in seen["cmd"], "must not match command lines"

    monkeypatch.setattr(play, "run", lambda cmd, **kw: Proc(1, "", ""))
    assert play.steam_running() is False


def test_stale_helpers_are_cleaned_before_starting_steam(monkeypatch):
    from cs2kit.util import Proc

    killed = []

    def fake_run(cmd, **kw):
        if cmd[0] == "pgrep" and cmd[-1] == "steam.exe":
            return Proc(1, "", "")                          # client not running
        if cmd[0] == "pgrep":
            return Proc(0, "123", "")                       # a stale helper
        if cmd[0] == "kill":
            killed.extend(cmd[2:])
            return Proc(0, "", "")
        return Proc(1, "", "")

    monkeypatch.setattr(play, "run", fake_run)
    assert play.clean_stale_steam() == ["123", "123"]
    assert killed, "orphaned helpers block a new client from starting"


def test_a_steam_update_re_baselines_itself(sandbox, cs2_tree, monkeypatch, capsys):
    """A new buildid is an update, not tampering: the guard re-arms silently.
    Non-technical users must never have to run `verify baseline` by hand."""
    make_bottle(sandbox)
    integrity.create_baseline()
    # Steam updates the game: files change AND the buildid moves.
    (cs2_tree / "client.dll").write_bytes(b"MZ-new-build")
    manifest = sandbox.steam / "steamapps" / "appmanifest_730.acf"
    manifest.write_text(manifest.read_text().replace("24828357", "24916958"))
    monkeypatch.setattr(play, "steam_running", lambda: True)

    assert play.cmd_play(args(print_only=True)) == EXIT_OK
    out = capsys.readouterr().out
    assert "re-baselined" in out and "24828357 -> 24916958" in out
    assert integrity.verify().status == PASS


def test_tampering_within_one_build_still_refuses(sandbox, cs2_tree, monkeypatch, capsys):
    make_bottle(sandbox)
    integrity.create_baseline()
    (cs2_tree / "client.dll").write_bytes(b"MZ-tampered")   # same buildid
    monkeypatch.setattr(play, "steam_running", lambda: True)
    assert play.cmd_play(args(print_only=True)) == EXIT_INTEGRITY


def test_the_default_launch_goes_through_steam(sandbox, cs2_tree, monkeypatch, capsys):
    """Launching cs2.exe directly makes VAC refuse every secure server:
    "game files have no signatures or invalid signatures" (measured 2026-08-25)."""
    make_bottle(sandbox)
    integrity.create_baseline()
    monkeypatch.setattr(play, "steam_running", lambda: True)

    assert play.cmd_play(args(json=True)) == EXIT_OK
    plan = json.loads(capsys.readouterr().out)
    assert plan["via"] == "steam"
    assert "-applaunch" in plan["command"] and "730" in plan["command"]
    assert plan["command"][1].lower().endswith("steam.exe")


def test_direct_launch_is_opt_in_only(sandbox, cs2_tree, monkeypatch, capsys):
    make_bottle(sandbox)
    integrity.create_baseline()
    monkeypatch.setattr(play, "steam_running", lambda: True)
    assert play.cmd_play(args(json=True, direct=True)) == EXIT_OK
    plan = json.loads(capsys.readouterr().out)
    assert plan["via"] == "direct" and plan["command"][1] == "cs2.exe"


def test_steam_only_hands_over_instead_of_launching(sandbox, cs2_tree, monkeypatch, capsys):
    """The launcher app opens Steam and stops: pressing Play there is the only
    path that gives CS2 its Steam context (VAC signatures, cloud settings)."""
    make_bottle(sandbox)
    integrity.create_baseline()
    monkeypatch.setattr(play, "steam_running", lambda: True)
    assert play.cmd_play(args(steam_only=True, json=False, print_only=False)) == EXIT_OK
    assert "Press Play" in capsys.readouterr().out
