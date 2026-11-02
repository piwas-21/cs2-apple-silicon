"""Shutdown authority is a prefix-scoped wineserver, never a global PID match."""
import argparse
import json

import pytest

from cs2kit import bottle, stop as stop_mod
from cs2kit.util import EXIT_FAIL, EXIT_OK, Proc, write_json


def engine_for(prefix, root):
    (root / "lib/wine").mkdir(parents=True)
    (root / "bin").mkdir()
    (root / "bin/wineserver").write_text("fake")
    (prefix / "system.reg").write_text("registry")
    write_json(bottle.state_file(prefix), {"wine_root": str(root)})
    return root / "bin/wineserver"


@pytest.mark.parametrize("force,flag", [(False, "-k"), (True, "-k9")])
def test_shutdown_uses_only_the_selected_prefix(monkeypatch, sandbox, force, flag):
    selected = sandbox.root / "other prefix"
    selected.mkdir()
    server = engine_for(selected, sandbox.root / "selected-engine")
    engine_for(sandbox.prefix, sandbox.root / "default-engine")
    calls = []

    def fake_run(cmd, **kw):
        calls.append((cmd, kw["env"]))
        return Proc(0, "", "")

    monkeypatch.setattr(stop_mod, "run", fake_run)
    result = stop_mod.stop(selected, force=force, log=lambda m: None)
    assert result["ok"] and result["wineserver_killed"]
    assert calls == [([str(server), flag], {"WINEPREFIX": str(selected.resolve())}),
                     ([str(server), "-w"], {"WINEPREFIX": str(selected.resolve())})]
    assert not any(cmd[0] in ("pgrep", "ps", "kill") for cmd, _ in calls)


def test_missing_prefix_is_a_noop(monkeypatch, sandbox, capsys):
    monkeypatch.setattr(stop_mod, "run", lambda *a, **kw: pytest.fail("missing prefix must not run anything"))
    args = argparse.Namespace(prefix=str(sandbox.prefix), force=False, json=True)
    assert stop_mod.cmd_stop(args) == EXIT_OK
    assert json.loads(capsys.readouterr().out)["ok"]


def test_shutdown_without_an_engine_fails_without_signalling(monkeypatch, sandbox, capsys):
    (sandbox.prefix / "system.reg").write_text("registry")
    monkeypatch.setattr(bottle, "wine_root", lambda **kw: None)
    monkeypatch.setattr(stop_mod, "run", lambda *a, **kw: pytest.fail("no engine must not run anything"))
    args = argparse.Namespace(prefix=str(sandbox.prefix), force=False, json=True)
    assert stop_mod.cmd_stop(args) == EXIT_FAIL
    payload = json.loads(capsys.readouterr().out)
    assert not payload["ok"] and "no processes were signalled" in payload["detail"]


@pytest.mark.parametrize("code", [124, 127, 2])
def test_shutdown_errors_are_not_reported_as_success(monkeypatch, sandbox, code):
    engine_for(sandbox.prefix, sandbox.root / "engine")
    monkeypatch.setattr(stop_mod, "run", lambda *a, **kw: Proc(code, "", "failed"))
    assert not stop_mod.stop(sandbox.prefix, log=lambda m: None)["ok"]
