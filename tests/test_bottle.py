import argparse

import pytest

from cs2kit import bottle, recipe as recipe_mod
from cs2kit.util import EXIT_FAIL, EXIT_NOT_READY, EXIT_OK, FAIL, PASS, WARN, Proc


class FakeRunner(bottle.WineRunner):
    """Records wine invocations and answers `reg query` from an in-memory registry."""

    def __init__(self, prefix, registry=None, **kw):
        super().__init__(prefix=prefix, **kw)
        self.wine = "/fake/wine"
        self.registry = dict(registry or {})

    def __call__(self, *args, timeout=180.0):
        self.log.append(["wine", *args])
        if args[:2] == ("reg", "add"):
            key, name, value = args[2], args[4], args[8]
            self.registry[(key, name)] = value
            return Proc(0, "", "")
        if args[:2] == ("reg", "query"):
            key, name = args[2], args[4]
            if (key, name) not in self.registry:
                return Proc(1, "", "not found")
            return Proc(0, f"{key}\n    {name}    REG_SZ    {self.registry[(key, name)]}", "")
        return Proc(0, "", "")


def rec(sandbox):
    return recipe_mod.load_default()


def test_desired_registry_covers_overrides_and_the_cs2_audio_fix(sandbox):
    triples = bottle.desired_registry(rec(sandbox))
    flat = {(k.split("Wine")[-1], n): v for k, n, v in triples}
    assert flat[("", "Version")] == "win10"
    assert flat[(r"\DllOverrides", "d3d11")].startswith("native")
    assert flat[(r"\AppDefaults\cs2.exe", "Version")] == "win8"


def test_create_writes_state_and_registry(sandbox):
    runner = FakeRunner(sandbox.prefix)
    result = bottle.create(rec(sandbox), prefix=sandbox.prefix, runner=runner)
    assert ["wine", "wineboot", "--init"] == runner.log[0]
    state = bottle.read_state(sandbox.prefix)
    assert state["recipe_name"] == "cs2-default"
    assert state["recipe_hash"] == rec(sandbox).hash()
    assert runner.registry[(bottle.WINE_KEY, "Version")] == "win10"


def test_create_refuses_an_invalid_recipe(sandbox):
    bad = recipe_mod.loads("schema: 1\nkind: bottle\nname: bad\n")
    with pytest.raises(recipe_mod.RecipeError):
        bottle.create(bad, prefix=sandbox.prefix, runner=FakeRunner(sandbox.prefix))


def test_dry_run_touches_nothing(sandbox):
    bottle.create(rec(sandbox), prefix=sandbox.prefix, dry_run=True,
                  runner=FakeRunner(sandbox.prefix, dry_run=True))
    assert not bottle.state_file(sandbox.prefix).exists()


def test_diff_finds_drift_and_repair_fixes_it(sandbox):
    recipe = rec(sandbox)
    runner = FakeRunner(sandbox.prefix)
    bottle.create(recipe, prefix=sandbox.prefix, runner=runner)
    assert bottle.diff(recipe, sandbox.prefix, runner) == {}

    runner.registry[(bottle.WINE_KEY + r"\DllOverrides", "d3d11")] = "builtin"
    drift = bottle.diff(recipe, sandbox.prefix, runner)
    assert r"Wine\DllOverrides\d3d11" in drift
    assert drift[r"Wine\DllOverrides\d3d11"]["actual"] == "builtin"

    result = bottle.repair(recipe, sandbox.prefix, runner)
    assert result["fixed"] == [r"Wine\DllOverrides\d3d11"]
    assert bottle.diff(recipe, sandbox.prefix, runner) == {}


def test_install_dxmt_requires_the_full_file_set(sandbox, tmp_path):
    source = tmp_path / "dxmt"
    (source / "x64").mkdir(parents=True)
    with pytest.raises(bottle.BottleError):
        bottle.install_dxmt(rec(sandbox), source, sandbox.prefix)
    for name in rec(sandbox).dxmt_files:
        (source / "x64" / name).write_bytes(b"dll")
    system32 = sandbox.prefix / "drive_c" / "windows" / "system32"
    system32.mkdir(parents=True)
    copied = bottle.install_dxmt(rec(sandbox), source, sandbox.prefix)
    assert (system32 / "d3d11.dll").is_file() and len(copied) == len(rec(sandbox).dxmt_files)


def test_drift_check_states(sandbox):
    check = bottle.drift_check(prefix=sandbox.prefix)
    assert check.status == FAIL and check.fix == "cs2kit bottle create"

    (sandbox.prefix / "system.reg").write_text("WINE REGISTRY")
    assert bottle.drift_check(prefix=sandbox.prefix).status == WARN  # not built by cs2kit

    bottle.create(rec(sandbox), prefix=sandbox.prefix, runner=FakeRunner(sandbox.prefix))
    assert bottle.drift_check(prefix=sandbox.prefix).status == PASS


def test_cmd_diff_exit_codes(sandbox, monkeypatch, capsys):
    monkeypatch.setattr(bottle, "which", lambda name: None)  # no wine on this machine
    args = argparse.Namespace(recipe=None, prefix=str(sandbox.prefix), json=False, dry_run=False)
    assert bottle.cmd_diff(args) == EXIT_NOT_READY          # no prefix yet
    (sandbox.prefix / "system.reg").write_text("WINE REGISTRY")
    assert bottle.cmd_diff(args) == EXIT_FAIL               # unreadable registry is drift
    assert "expected" in capsys.readouterr().out
