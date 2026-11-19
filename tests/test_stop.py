"""`cs2kit stop` never signals a process it cannot bind to the chosen bottle."""
import argparse
import json

import pytest

from cs2kit import bottle, procs, stop as stop_mod
from cs2kit.util import EXIT_FAIL, EXIT_OK, Proc, write_json


def engine_for(prefix, root):
    (root / "lib" / "wine").mkdir(parents=True)
    (root / "bin").mkdir(parents=True, exist_ok=True)
    (root / "bin" / "wineserver").write_text("fake")
    (prefix / "system.reg").write_text("registry")
    write_json(bottle.state_file(prefix), {"wine_root": str(root)})
    return root / "bin" / "wineserver"


def test_shutdown_is_scoped_to_the_selected_prefix(monkeypatch, sandbox):
    selected = sandbox.root / "other prefix"
    selected.mkdir()
    server = engine_for(selected, sandbox.root / "selected-engine")
    engine_for(sandbox.prefix, sandbox.root / "default-engine")
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw.get("env")))
        return Proc(0, "", "")

    monkeypatch.setattr(stop_mod, "run", fake_run)
    result = stop_mod.stop(selected, log=lambda m: None)
    assert result["ok"] and result["wineserver_killed"]
    scoped = [call for call in calls if call[0][0] == str(server)]
    assert scoped == [([str(server), "-k"], {"WINEPREFIX": str(selected)}),
                      ([str(server), "-w"], {"WINEPREFIX": str(selected)})]
    assert not any(cmd[0] in ("pgrep", "kill") for cmd, _ in calls)
    assert all(cmd[0] == "ps" for cmd, _ in calls
               if cmd[0] not in (str(server), "kill", "pgrep"))


def test_force_still_scopes_kill_to_the_selected_prefix(monkeypatch, sandbox):
    server = engine_for(sandbox.prefix, sandbox.root / "engine")
    calls = []
    monkeypatch.setattr(stop_mod, "run",
                        lambda cmd, **kw: calls.append((cmd, kw.get("env"))) or Proc(0, "", ""))
    assert stop_mod.stop(sandbox.prefix, force=True, log=lambda m: None)["ok"]
    kill = [call for call in calls if call[0][0] == str(server) and "-k9" in call[0]]
    assert kill == [([str(server), "-k9"], {"WINEPREFIX": str(sandbox.prefix)})]


def test_idle_bottle_is_not_an_error(monkeypatch, sandbox, capsys):
    monkeypatch.setattr(stop_mod, "run", lambda cmd, **kw: Proc(1, "", ""))
    args = argparse.Namespace(prefix=str(sandbox.prefix), force=False, json=False)
    assert stop_mod.cmd_stop(args) == EXIT_OK
    assert "nothing was running" in capsys.readouterr().out


def test_shutdown_without_a_server_signals_nothing(monkeypatch, sandbox, capsys):
    (sandbox.prefix / "system.reg").write_text("registry")
    monkeypatch.setattr(stop_mod, "run",
                        lambda *a, **kw: pytest.fail("no server must not run anything"))
    args = argparse.Namespace(prefix=str(sandbox.prefix), force=False, json=True)
    assert stop_mod.cmd_stop(args) == EXIT_FAIL
    out = capsys.readouterr().out
    payload = json.loads(out[out.index("{"):])
    assert not payload["ok"] and "no processes were signalled" in payload["detail"]


def test_malformed_process_names_and_shells_are_not_candidates(monkeypatch, sandbox):
    """`tail -f /logs/steam.exe` and `/bin/sh -c echo steam.exe` mention the
    name as an argument; neither is the Wine executable."""
    from cs2kit.util import Proc

    def fake_run(cmd, **kw):
        if cmd == ["ps", "-axww", "-o", "pid=,comm="]:
            return Proc(0, "\n".join([
                "501 /usr/bin/tail", "502 /bin/sh", "503 bash", "504 /usr/sbin/cupsd"]), "")
        return Proc(1, "", "")

    monkeypatch.setattr(stop_mod, "run", fake_run)
    assert stop_mod.pids("steam.exe", sandbox.prefix) == []


def test_wow64_process_in_the_selected_prefix_is_a_candidate(monkeypatch, sandbox):
    from cs2kit.util import Proc

    def fake_run(cmd, **kw):
        if cmd == ["ps", "-axww", "-o", "pid=,comm="]:
            return Proc(0, "42 C:\\Program Files (x86)\\Steam\\steam.exe\n", "")
        if cmd == ["ps", "eww", "-p", "42", "-o", "command="]:
            return Proc(0, f"steam.exe WINEPREFIX={sandbox.prefix} PATH=/bin", "")
        return Proc(1, "", "")

    monkeypatch.setattr(stop_mod, "run", fake_run)
    assert stop_mod.pids("steam.exe", sandbox.prefix) == ["42"]


def test_two_active_prefixes_are_distinguished(monkeypatch, sandbox):
    other = sandbox.root / "other bottle"
    other.mkdir()
    from cs2kit.util import Proc

    def fake_run(cmd, **kw):
        if cmd == ["ps", "-axww", "-o", "pid=,comm="]:
            return Proc(0, "41 steam.exe\n42 steam.exe\n", "")
        owners = {"41": sandbox.prefix, "42": other}
        return Proc(0, f"steam.exe WINEPREFIX={owners[cmd[3]]} PATH=/bin", "")

    monkeypatch.setattr(stop_mod, "run", fake_run)
    assert stop_mod.pids("steam.exe", sandbox.prefix) == ["41"]
    assert stop_mod.pids("steam.exe", other) == ["42"]


def test_ambiguous_candidates_are_reported_but_never_signalled(monkeypatch, sandbox):
    engine_for(sandbox.prefix, sandbox.root / "engine")
    log = []
    signalled = []

    def fake_run(cmd, **kw):
        if cmd == ["ps", "-axww", "-o", "pid=,comm="]:
            return Proc(0, "41 steam.exe\n42 steam.exe\n", "")
        if cmd[:2] == ["ps", "eww"]:
            return Proc(0, "steam.exe PATH=/bin", "")       # ownership unknown
        if cmd[0] in ("kill", "pgrep"):
            signalled.append(cmd)
        return Proc(0, "", "")

    monkeypatch.setattr(stop_mod, "run", fake_run)
    result = stop_mod.stop(sandbox.prefix, log=log.append)
    assert not signalled, "ambiguous PIDs must not enter a TERM/KILL path"
    assert result["ambiguous"]["steam.exe"] == ["41", "42"]
    assert result["stopped"] == {}
    assert any("unproven prefix" in message for message in log)


def test_shared_selection_reports_ambiguity(monkeypatch, sandbox):
    """Both commands use the same helper, so an unreadable process is refused
    in exactly the same way before any caller can act on it."""
    from cs2kit.util import Proc

    def runner(cmd, **kw):
        if cmd == ["ps", "-axww", "-o", "pid=,comm="]:
            return Proc(0, "41 steam.exe\n42 steam.exe\n", "")
        if cmd[3] == "41":
            return Proc(0, f"steam.exe WINEPREFIX={sandbox.prefix}", "")
        return Proc(1, "", "process exited")

    selection = procs.select("steam.exe", sandbox.prefix, runner=runner)
    assert selection.pids == []
    assert selection.ambiguous == ["42"]
