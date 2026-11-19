
"""`cs2kit play` is what the launcher app runs, so its refusals are the app's UX."""
import argparse
import json
from pathlib import Path

import pytest

from cs2kit import integrity, play, probe
from cs2kit.util import EXIT_INTEGRITY, EXIT_NOT_READY, EXIT_OK, PASS


@pytest.fixture(autouse=True)
def isolate_native_steam(monkeypatch):
    """Play must not depend on whether the developer's own Steam is open."""
    monkeypatch.setattr(play, "native_steam_running", lambda: False)


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
    monkeypatch.setattr(play, "steam_running", lambda *a, **kw: True)
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
    monkeypatch.setattr(play, "steam_running", lambda *a, **kw: True)
    assert play.cmd_play(args(json=True)) == EXIT_NOT_READY
    assert "install CS2" in json.loads(capsys.readouterr().out)["detail"]


def test_the_plan_is_resolved_from_disk_not_baked(sandbox, cs2_tree, monkeypatch):
    make_bottle(sandbox)
    monkeypatch.setattr(play, "steam_running", lambda *a, **kw: True)
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
def test_steam_running_matches_the_wine_executable(sandbox, monkeypatch, executable):
    """Wine's wow64 loader can carry the Windows path in `comm`; a bare mention
    in a shell argument is not the executable and must never be selected."""
    from cs2kit.util import Proc

    def fake_run(cmd, **kw):
        if cmd == ["ps", "-axww", "-o", "pid=,comm="]:
            return Proc(0, "4242 " + executable + "\n", "")
        if cmd == ["ps", "eww", "-p", "4242", "-o", "command="]:
            return Proc(0, f"steam.exe WINEPREFIX={sandbox.prefix} PATH=/bin", "")
        return Proc(1, "", "")

    monkeypatch.setattr(play, "run", fake_run)
    assert play._pids("steam.exe", sandbox.prefix) == ["4242"]
    assert play.steam_running(sandbox.prefix) is False  # no wineserver for this bottle


def test_steam_running_ignores_shells_and_unrelated_path_arguments(sandbox, monkeypatch):
    from cs2kit.util import Proc

    def fake_run(cmd, **kw):
        if cmd == ["ps", "-axww", "-o", "pid=,comm="]:
            return Proc(0, "\n".join([
                "501 /bin/sh", "502 tail", "503 python3", "504 /usr/sbin/cupsd"]), "")
        return Proc(1, "", "")

    monkeypatch.setattr(play, "run", fake_run)
    assert play._pids("steam.exe", sandbox.prefix) == []
    assert play.steam_running(sandbox.prefix) is False


def test_steam_running_ignores_a_husk_whose_wineserver_is_gone(sandbox, monkeypatch):
    """A steam.exe without this bottle's wineserver is debris: counting it made
    every launch skip starting Steam and send -applaunch into a dead process."""
    from cs2kit.util import Proc

    def fake_run(cmd, **kw):
        if cmd == ["ps", "-axww", "-o", "pid=,comm="]:
            return Proc(0, "500 C:\\Program Files (x86)\\Steam\\steam.exe\n", "")
        if cmd == ["ps", "eww", "-p", "500", "-o", "command="]:
            return Proc(0, f"steam.exe WINEPREFIX={sandbox.prefix} PATH=/bin", "")
        return Proc(1, "", "")

    monkeypatch.setattr(play, "run", fake_run)
    assert play._pids("steam.exe", sandbox.prefix) == ["500"]
    assert play.steam_running(sandbox.prefix) is False


def test_two_active_prefixes_do_not_confuse_steam_running(sandbox, monkeypatch):
    other = sandbox.root / "other bottle"
    other.mkdir()

    def fake_run(cmd, **kw):
        from cs2kit.util import Proc
        if cmd == ["ps", "-axww", "-o", "pid=,comm="]:
            return Proc(0, "41 steam.exe\n42 steam.exe\n43 wineserver\n44 wineserver\n", "")
        pid = cmd[3]
        owners = {"41": sandbox.prefix, "42": other, "43": sandbox.prefix, "44": other}
        return Proc(0, f"wine WINEPREFIX={owners[pid]} PATH=/bin", "")

    monkeypatch.setattr(play, "run", fake_run)
    assert play.steam_running(sandbox.prefix) is True
    assert play.steam_running(other) is True
    missing = sandbox.root / "empty bottle"
    missing.mkdir()
    assert play.steam_running(missing) is False


def test_ambiguous_processes_never_count_as_running(sandbox, monkeypatch):
    def fake_run(cmd, **kw):
        from cs2kit.util import Proc
        if cmd == ["ps", "-axww", "-o", "pid=,comm="]:
            return Proc(0, "41 steam.exe\n42 steam.exe\n", "")
        return Proc(0, "wine PATH=/bin", "")       # no WINEPREFIX on either

    monkeypatch.setattr(play, "run", fake_run)
    assert play._pids("steam.exe", sandbox.prefix) == []
    assert play.steam_running(sandbox.prefix) is False


def test_launcher_never_kills_unowned_helpers(monkeypatch):
    """A PID found by name cannot establish prefix ownership; global SIGKILL
    from the launcher can take down another bottle (review of PR #1)."""
    def forbidden(cmd, **kw):
        if cmd[0] in ("kill", "pgrep"):
            pytest.fail(f"launcher signalled or searched by name: {cmd}")
        from cs2kit.util import Proc
        return Proc(1, "", "")

    monkeypatch.setattr(play, "run", forbidden)
    assert play.clean_stale_steam() == []


def test_a_steam_update_re_baselines_itself(sandbox, cs2_tree, monkeypatch, capsys):
    """A new buildid is an update, not tampering: the guard re-arms silently.
    Non-technical users must never have to run `verify baseline` by hand."""
    make_bottle(sandbox)
    integrity.create_baseline()
    # Steam updates the game: files change AND the buildid moves.
    (cs2_tree / "client.dll").write_bytes(b"MZ-new-build")
    manifest = sandbox.steam / "steamapps" / "appmanifest_730.acf"
    manifest.write_text(manifest.read_text().replace("24828357", "24916958"))
    monkeypatch.setattr(play, "steam_running", lambda *a, **kw: True)

    assert play.cmd_play(args(print_only=True)) == EXIT_OK
    out = capsys.readouterr().out
    assert "re-baselined" in out and "24828357 -> 24916958" in out
    assert integrity.verify().status == PASS


def test_tampering_within_one_build_still_refuses(sandbox, cs2_tree, monkeypatch, capsys):
    make_bottle(sandbox)
    integrity.create_baseline()
    (cs2_tree / "client.dll").write_bytes(b"MZ-tampered")   # same buildid
    monkeypatch.setattr(play, "steam_running", lambda *a, **kw: True)
    assert play.cmd_play(args(print_only=True)) == EXIT_INTEGRITY


def test_the_default_launch_goes_through_steam(sandbox, cs2_tree, monkeypatch, capsys):
    """Launching cs2.exe directly makes VAC refuse every secure server:
    "game files have no signatures or invalid signatures" (measured 2026-08-25)."""
    make_bottle(sandbox)
    integrity.create_baseline()
    monkeypatch.setattr(play, "steam_running", lambda *a, **kw: True)

    assert play.cmd_play(args(json=True)) == EXIT_OK
    plan = json.loads(capsys.readouterr().out)
    assert plan["via"] == "steam"
    assert "-applaunch" in plan["command"] and "730" in plan["command"]
    assert plan["command"][1].lower().endswith("steam.exe")


def test_direct_launch_is_opt_in_only(sandbox, cs2_tree, monkeypatch, capsys):
    make_bottle(sandbox)
    integrity.create_baseline()
    monkeypatch.setattr(play, "steam_running", lambda *a, **kw: True)
    assert play.cmd_play(args(json=True, direct=True)) == EXIT_OK
    plan = json.loads(capsys.readouterr().out)
    assert plan["via"] == "direct" and plan["command"][1] == "cs2.exe"


def test_steam_only_hands_over_instead_of_launching(sandbox, cs2_tree, monkeypatch, capsys):
    """The launcher app opens Steam and stops: pressing Play there is the only
    path that gives CS2 its Steam context (VAC signatures, cloud settings)."""
    make_bottle(sandbox)
    integrity.create_baseline()
    monkeypatch.setattr(play, "steam_running", lambda *a, **kw: True)
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


def _write_connection_log(sandbox, stamp: str) -> None:
    logs = sandbox.prefix / "drive_c" / "Program Files (x86)" / "Steam" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "connection_log.txt").write_text(
        "[2020-01-01 00:00:00] older session noise\n"
        f"[{stamp}] [Logged On, 4, 7] [U:1:1] RecvMsgClientLogOnResponse() : 'OK'\n")


def test_steam_ready_ignores_a_logged_on_line_from_an_older_session(sandbox, monkeypatch):
    """connection_log.txt accumulates across sessions: yesterday's `Logged On` sat
    in the scanned tail, so the wait fired instantly and `-applaunch` hit the fresh
    client mid-handshake - Steam silently drops that, and the launcher app looks
    like it started nothing (measured 2026-11-10, right after the wedged client
    from 2026-11-08 was cleaned up). A line only counts when it is newer than the
    current steam.exe processes."""
    from datetime import datetime, timedelta

    from cs2kit.util import Proc

    monkeypatch.setattr(play, "_pids", lambda *a: ["123"])
    monkeypatch.setattr(play, "run",
                        lambda cmd, **kw: Proc(0, "00:10:00\n", ""))   # steam up 10 min
    stale = (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    fresh = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")

    _write_connection_log(sandbox, stale)
    assert play.steam_ready(sandbox.prefix, timeout=1) is False, \
        "a Logged On older than steam.exe is a previous session"

    _write_connection_log(sandbox, fresh)
    assert play.steam_ready(sandbox.prefix, timeout=1) is True, \
        "a Logged On from this session must be accepted at once"


def test_steam_ready_needs_a_client_to_be_running_at_all(sandbox, monkeypatch):
    """With no steam.exe process there is no session the `Logged On` line could
    belong to - it is history. Accepting it made the launcher send `-applaunch`
    into a client that was not there, and Steam drops that without a trace, so
    the app looked like it had started nothing (measured 2026-11-12)."""
    from datetime import datetime, timedelta

    from cs2kit.util import Proc

    monkeypatch.setattr(play, "_pids", lambda *a: [])      # no client at all
    monkeypatch.setattr(play, "run", lambda cmd, **kw: Proc(1, "", ""))
    fresh = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    _write_connection_log(sandbox, fresh)
    assert play.steam_ready(sandbox.prefix, timeout=1) is False, \
        "a Logged On without a running client is a previous session"


def _write_content_log(sandbox, line: str) -> None:
    logs = sandbox.prefix / "drive_c" / "Program Files (x86)" / "Steam" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "content_log.txt").write_text(line + "\n")


def test_an_update_in_progress_is_recognised(sandbox):
    """Steam turns `-applaunch` into a download when the installed build is
    stale, and the game appears only when the download is done - minutes later,
    with nothing on screen until then (measured 2026-11-12, a 1.1 GB update).
    The launcher has to be able to say that."""
    from datetime import datetime, timedelta

    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")
    old = (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")

    _write_content_log(sandbox, f"[{stamp}] AppID 730 state changed : Update Required,"
                                 "Fully Installed,Update Queued,Update Running,")
    assert play.updating_cs2(sandbox.prefix) is True

    _write_content_log(sandbox, f"[{stamp}] AppID 730 state changed : Fully Installed,"
                                 "App Running,")
    assert play.updating_cs2(sandbox.prefix) is False

    _write_content_log(sandbox, f"[{old}] AppID 730 state changed : Update Required,"
                                 "Fully Installed,")
    assert play.updating_cs2(sandbox.prefix) is False, \
        "a state line from a previous session says nothing about this launch"


def test_the_app_launches_without_becoming_the_game_and_says_so(sandbox, cs2_tree,
                                                               monkeypatch, capsys):
    """`execve` replaced the launcher with the game launcher, so nobody was left
    to tell the player that the game takes a minute - or that Steam is updating
    it first. In GUI mode the launcher has to survive the launch and report."""
    make_bottle(sandbox)
    integrity.create_baseline()
    monkeypatch.setattr(play, "steam_running", lambda *a, **kw: True)

    spawned = []
    told = []
    monkeypatch.setattr(play, "_spawn_launch",
                        lambda cmd, env, target_dir: spawned.append(cmd))
    monkeypatch.setattr(play, "notification", told.append)
    monkeypatch.setattr(play, "game_running", lambda: True)
    monkeypatch.setattr(play, "steam_ready", lambda prefix, timeout=90.0: True)

    assert play.cmd_play(args(gui=True, print_only=False)) == EXIT_OK
    assert spawned, "the GUI path must spawn the launch instead of execve'ing it"
    assert "-applaunch" in spawned[0]
    assert told and "CS2" in told[0], "the player must be told that the game is coming up"


def test_the_spawned_launch_outlives_the_launcher(monkeypatch, tmp_path):
    """An applet that exits takes its children with it, so the game launcher has
    to get its own session - and the app's log file - or it dies with the
    launcher that started it."""
    calls = {}

    class FakePopen:
        def __init__(self, cmd, **kw):
            calls["cmd"] = cmd
            calls["kw"] = kw

    monkeypatch.setattr(play.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(play.Path, "home", classmethod(lambda cls: tmp_path))
    play._spawn_launch(["wine", "steam.exe", "-applaunch", "730"], {"A": "B"}, tmp_path)
    assert calls["cmd"][1] == "steam.exe"
    assert calls["kw"]["start_new_session"] is True
    assert calls["kw"]["stdout"] is not None


def test_the_detached_worker_outlives_the_app_that_started_it(tmp_path):
    """The launcher app is a real application bundle. When it quits, macOS tears
    down its whole job - SIGTERM to every process still in it, however well it
    hid. The detached worker was killed a second into the launch, before it had
    even started Steam, so the app did nothing at all and looked broken
    (measured 2026-11-12, repeatedly). A daemon has to outlive its parent."""
    import subprocess
    import sys
    import textwrap
    import time

    from cs2kit.util import repo_root

    marker = tmp_path / "signals.txt"
    script = textwrap.dedent(f"""
        import signal, sys
        sys.path.insert(0, {str(repo_root())!r})
        from cs2kit.play import daemonize
        daemonize({str(tmp_path / "worker.log")!r})
        ignored = (signal.getsignal(signal.SIGTERM) == signal.SIG_IGN
                   and signal.getsignal(signal.SIGHUP) == signal.SIG_IGN)
        open({str(marker)!r}, "w").write("ignored" if ignored else "not ignored")
    """)
    subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                   timeout=60)
    deadline = time.time() + 15
    while time.time() < deadline and not marker.exists():
        time.sleep(0.2)
    assert marker.exists(), "the detached worker did not survive its parent"
    assert marker.read_text() == "ignored", \
        "the worker must ignore the signals that say 'your parent is gone'"


def test_native_macos_steam_blocks_the_launch(sandbox, monkeypatch, capsys):
    """The native macOS client cannot run CS2 and takes over the account session
    the Wine client needs, so every -applaunch into the bottle is silently
    dropped - the launcher 'opened' nothing while it ran (measured 2026-11-10/11).
    play must refuse loudly instead of no-opping."""
    notified = []
    monkeypatch.setattr(play, "native_steam_running", lambda: True)
    monkeypatch.setattr(play, "notify", notified.append)
    assert play.cmd_play(args(gui=True, json=True, print_only=False)) == EXIT_NOT_READY
    assert "Native Steam" in json.loads(capsys.readouterr().out)["detail"]
    assert notified and "quit native Steam" in notified[0]
