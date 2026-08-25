
"""`cs2kit stop`: quitting Wine from the menu bar does not stop anything."""
import argparse
import json

from cs2kit import stop as stop_mod
from cs2kit.util import EXIT_OK, Proc


def test_it_stops_the_youngest_process_first(monkeypatch, sandbox):
    order = []
    alive = {"cs2.exe": ["11"], "steam.exe": ["22"], "steamwebhelper.exe": ["33"],
             "steamservice.exe": ["44"]}

    def fake_run(cmd, **kw):
        if cmd[0] == "pgrep":
            name = cmd[-1]
            return Proc(0, " ".join(alive.get(name, [])), "") if alive.get(name) else Proc(1, "", "")
        if cmd[0] == "kill":
            for name, pids in alive.items():
                if set(pids) & set(cmd[2:]):
                    order.append(name)
                    alive[name] = []
            return Proc(0, "", "")
        return Proc(0, "", "")

    monkeypatch.setattr(stop_mod, "run", fake_run)
    result = stop_mod.stop(sandbox.prefix, log=lambda m: None)
    assert order == stop_mod.STAGES, "the game must go before Steam, helpers after"
    assert result["stopped"] == {name: 1 for name in stop_mod.STAGES}


def test_stopping_an_idle_bottle_is_not_an_error(monkeypatch, sandbox, capsys):
    monkeypatch.setattr(stop_mod, "run", lambda cmd, **kw: Proc(1, "", ""))
    args = argparse.Namespace(prefix=str(sandbox.prefix), force=False, json=False)
    assert stop_mod.cmd_stop(args) == EXIT_OK
    assert "nothing was running" in capsys.readouterr().out
