
"""`cs2kit play` is what the launcher app runs, so its refusals are the app's UX."""
import argparse
import json

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
    monkeypatch.setattr(play, "steam_running", lambda *a: True)
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
    monkeypatch.setattr(play, "steam_running", lambda *a: True)
    assert play.cmd_play(args(json=True)) == EXIT_NOT_READY
    assert "install CS2" in json.loads(capsys.readouterr().out)["detail"]


def test_the_plan_is_resolved_from_disk_not_baked(sandbox, cs2_tree, monkeypatch):
    make_bottle(sandbox)
    monkeypatch.setattr(play, "steam_running", lambda *a: True)
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


@pytest.mark.parametrize("executable", [
    "steam.exe", r"C:\Program Files (x86)\Steam\steam.exe",
    "/bottle/drive_c/Program Files (x86)/Steam/Steam.exe",
])
def test_steam_running_matches_executable_basename(sandbox, monkeypatch, executable):
    from cs2kit.util import Proc

    def fake_run(cmd, **kw):
        if cmd == ["ps", "-axww", "-o", "pid=,comm="]:
            return Proc(0, "4242 " + executable + "\n", "")
        assert cmd == ["ps", "eww", "-p", "4242", "-o", "command="]
        return Proc(0, f"steam.exe WINEPREFIX={sandbox.prefix} PATH=/bin", "")

    monkeypatch.setattr(play, "run", fake_run)
    assert play.steam_running() is True


def test_steam_detection_ignores_helpers_and_shell_arguments(sandbox, monkeypatch):
    from cs2kit.util import Proc

    listing = ("21 /bin/zsh\n22 /bin/bash\n"
               "23 C:\\Steam\\steamservice.exe\n24 C:\\Steam\\steamwebhelper.exe\n"
               "25 /bin/zsh -c wine steam.exe\n26 /tmp/notsteam.exe\ninvalid\n")
    monkeypatch.setattr(play, "run", lambda cmd, **kw: Proc(0, listing, ""))
    assert play.steam_running() is False
    monkeypatch.setattr(play, "run", lambda cmd, **kw: Proc(1, "", "ps failed"))
    assert play.steam_running() is False


@pytest.mark.parametrize("ownership", ["other", "missing", "relative", "unreadable"])
def test_steam_in_another_bottle_cannot_suppress_startup(sandbox, monkeypatch, ownership):
    from cs2kit.util import Proc

    selected = sandbox.root / "selected bottle"
    selected.mkdir()
    owner = {"other": str(sandbox.prefix), "missing": "", "relative": "."}.get(ownership, "")
    def fake_run(cmd, **kw):
        if cmd == ["ps", "-axww", "-o", "pid=,comm="]:
            return Proc(0, "42 C:\\Steam\\steam.exe\n", "")
        assert cmd == ["ps", "eww", "-p", "42", "-o", "command="]
        if ownership == "unreadable":
            return Proc(1, "", "process exited")
        return Proc(0, f"steam.exe WINEPREFIX={owner} PATH=/bin", "")
    monkeypatch.setattr(play, "run", fake_run)
    assert not play.steam_running(selected)


def test_steam_ownership_handles_spaces_aliases_and_multiple_clients(sandbox, monkeypatch):
    from cs2kit.util import Proc

    selected = sandbox.root / "selected bottle"
    selected.mkdir()
    alias = sandbox.root / "bottle-alias"
    alias.symlink_to(selected, target_is_directory=True)
    def fake_run(cmd, **kw):
        if cmd == ["ps", "-axww", "-o", "pid=,comm="]:
            return Proc(0, "41 steam.exe\n42 C:\\Steam\\steam.exe\n", "")
        owner = sandbox.prefix if cmd[3] == "41" else alias
        return Proc(0, f"steam.exe WINEPREFIX={owner} PATH=/bin", "")
    monkeypatch.setattr(play, "run", fake_run)
    assert play.steam_running(selected)


def test_play_starts_selected_bottle_when_only_another_client_runs(
        sandbox, cs2_tree, monkeypatch, capsys):
    from cs2kit.util import Proc

    make_bottle(sandbox)
    integrity.create_baseline()
    selected = sandbox.root / "selected bottle"
    selected.mkdir()
    checked, started = [], []
    def fake_run(cmd, **kw):
        if cmd == ["ps", "-axww", "-o", "pid=,comm="]:
            return Proc(0, "42 C:\\Steam\\steam.exe\n", "")
        checked.append(cmd)
        return Proc(0, f"steam.exe WINEPREFIX={sandbox.prefix} PATH=/bin", "")
    monkeypatch.setattr(play, "run", fake_run)
    monkeypatch.setattr(play, "diagnose", lambda prefix: None)
    monkeypatch.setattr(play, "steam_client", lambda prefix: prefix / "Steam.exe")
    monkeypatch.setattr(play, "_start_steam", lambda prefix, *a: started.append(prefix))
    assert play.cmd_play(args(prefix=str(selected), steam_only=True, print_only=False)) == EXIT_OK
    assert started == [selected] and checked
    assert "Press Play" in capsys.readouterr().out


def test_starting_steam_does_not_kill_unowned_helpers(monkeypatch):
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
    assert play.clean_stale_steam() == []
    assert not killed, "a global name match cannot establish prefix ownership"


def test_a_steam_update_re_baselines_itself(sandbox, cs2_tree, monkeypatch, capsys):
    """A new buildid is an update, not tampering: the guard re-arms silently.
    Non-technical users must never have to run `verify baseline` by hand."""
    make_bottle(sandbox)
    integrity.create_baseline()
    # Steam updates the game: files change AND the buildid moves.
    (cs2_tree / "client.dll").write_bytes(b"MZ-new-build")
    manifest = sandbox.steam / "steamapps" / "appmanifest_730.acf"
    manifest.write_text(manifest.read_text().replace("24828357", "24916958"))
    monkeypatch.setattr(play, "steam_running", lambda *a: True)

    # Exercise a real launch path; previews must never write a new baseline.
    assert play.cmd_play(args(print_only=False, steam_only=True)) == EXIT_OK
    out = capsys.readouterr().out
    assert "re-baselined" in out and "24828357 -> 24916958" in out
    assert integrity.verify().status == PASS


def forbid_play_side_effects(monkeypatch):
    def forbidden(*a, **kw):
        pytest.fail("a print-only invocation performed a launch side effect")

    for name in ("_start_steam", "steam_ready", "daemonize", "notify"):
        monkeypatch.setattr(play, name, forbidden)
    monkeypatch.setattr(play.os, "execve", forbidden)
    monkeypatch.setattr(integrity, "create_baseline", forbidden)


@pytest.mark.parametrize("mode,via", [({}, "steam"), ({"direct": True}, "direct"),
                                    ({"steam_only": True}, "steam-ui")])
def test_print_only_does_not_launch_wait_detach_or_notify(
        sandbox, cs2_tree, monkeypatch, capsys, mode, via):
    make_bottle(sandbox)
    integrity.create_baseline()
    monkeypatch.setattr(play, "steam_running", lambda *a: False)
    forbid_play_side_effects(monkeypatch)

    assert play.cmd_play(args(detach=True, gui=True, **mode)) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["via"] == via


def test_print_only_missing_game_does_not_start_steam(sandbox, monkeypatch, capsys):
    make_bottle(sandbox)
    monkeypatch.setattr(play, "steam_running", lambda *a: False)
    forbid_play_side_effects(monkeypatch)

    assert play.cmd_play(args(json=True, gui=True)) == EXIT_NOT_READY
    assert "install CS2" in json.loads(capsys.readouterr().out)["detail"]


def test_print_only_integrity_failure_does_not_start_steam(
        sandbox, cs2_tree, monkeypatch, capsys):
    make_bottle(sandbox)
    integrity.create_baseline()
    (cs2_tree / "client.dll").write_bytes(b"modified")
    monkeypatch.setattr(play, "steam_running", lambda *a: False)
    forbid_play_side_effects(monkeypatch)

    assert play.cmd_play(args(json=True, gui=True)) == EXIT_INTEGRITY
    detail = json.loads(capsys.readouterr().out)["detail"]
    assert "Verify integrity" in detail and "Steam is opening" not in detail


def test_print_only_after_update_preserves_the_baseline(
        sandbox, cs2_tree, monkeypatch, capsys):
    make_bottle(sandbox)
    integrity.create_baseline()
    before = {p.name: p.read_bytes() for p in (sandbox.home / "integrity").glob("*.json")}
    manifest = sandbox.steam / "steamapps" / "appmanifest_730.acf"
    manifest.write_text(manifest.read_text().replace("24828357", "24916958"))
    (cs2_tree / "client.dll").write_bytes(b"new build")
    forbid_play_side_effects(monkeypatch)

    assert play.cmd_play(args(json=True)) == EXIT_OK
    json.loads(capsys.readouterr().out)  # No re-baseline progress before the JSON.
    after = {p.name: p.read_bytes() for p in (sandbox.home / "integrity").glob("*.json")}
    assert before and before == after
    assert integrity.verify().baseline_buildid == "24828357"


def test_tampering_within_one_build_still_refuses(sandbox, cs2_tree, monkeypatch, capsys):
    make_bottle(sandbox)
    integrity.create_baseline()
    (cs2_tree / "client.dll").write_bytes(b"MZ-tampered")   # same buildid
    monkeypatch.setattr(play, "steam_running", lambda *a: True)
    assert play.cmd_play(args(print_only=True)) == EXIT_INTEGRITY


def test_the_default_launch_goes_through_steam(sandbox, cs2_tree, monkeypatch, capsys):
    """Launching cs2.exe directly makes VAC refuse every secure server:
    "game files have no signatures or invalid signatures" (measured 2026-08-25)."""
    make_bottle(sandbox)
    integrity.create_baseline()
    monkeypatch.setattr(play, "steam_running", lambda *a: True)

    assert play.cmd_play(args(json=True)) == EXIT_OK
    plan = json.loads(capsys.readouterr().out)
    assert plan["via"] == "steam"
    assert "-applaunch" in plan["command"] and "730" in plan["command"]
    assert plan["command"][1].lower().endswith("steam.exe")


def test_direct_launch_is_opt_in_only(sandbox, cs2_tree, monkeypatch, capsys):
    make_bottle(sandbox)
    integrity.create_baseline()
    monkeypatch.setattr(play, "steam_running", lambda *a: True)
    assert play.cmd_play(args(json=True, direct=True)) == EXIT_OK
    plan = json.loads(capsys.readouterr().out)
    assert plan["via"] == "direct" and plan["command"][1] == "cs2.exe"


def test_app_launch_passes_profile_and_extra_options_to_steam(sandbox, cs2_tree, monkeypatch):
    from cs2kit import recipe

    make_bottle(sandbox)
    integrity.create_baseline()
    monkeypatch.setattr(play, "steam_running", lambda *a: True)
    monkeypatch.setattr(play, "steam_ready", lambda prefix: True)
    monkeypatch.setattr(play.os, "chdir", lambda path: None)
    executed = []
    monkeypatch.setattr(play.os, "execve", lambda exe, argv, env: executed.append((argv, env)))
    profile = "competitive-lowest-latency"
    assert play.cmd_play(args(profile=profile, extra=["-windowed"], print_only=False)) == EXIT_OK
    argv, env = executed[0]
    assert argv[2:] == ["-applaunch", "730", *recipe.resolve(profile).launch_options, "-windowed"]
    assert env["WINEPREFIX"] == str(sandbox.prefix)


def test_steam_only_hands_over_instead_of_launching(sandbox, cs2_tree, monkeypatch, capsys):
    """Explicit manual mode opens Steam without asking it to launch the game."""
    make_bottle(sandbox)
    integrity.create_baseline()
    monkeypatch.setattr(play, "steam_running", lambda *a: True)
    assert play.cmd_play(args(steam_only=True, json=False, print_only=False)) == EXIT_OK
    assert "Press Play" in capsys.readouterr().out


def test_game_running_sees_the_windows_path_steam_uses(monkeypatch):
    """Steam starts the game with its full Windows path, so an exact process-name
    match misses it. Our own shell wrappers must not count as the game."""
    from cs2kit.util import Proc

    monkeypatch.setattr(play, "run", lambda cmd, **kw: Proc(
        0, "bash -lc cd '/x' && wine cs2.exe -novid\n/usr/sbin/cupsd", ""))
    assert play.game_running() is False, "a shell mentioning cs2.exe is not the game"

    monkeypatch.setattr(play, "run", lambda cmd, **kw: Proc(
        0, "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Counter-Strike Global "
           "Offensive\\game\\bin\\win64\\cs2.exe -novid", ""))
    assert play.game_running() is True
