import argparse

import pytest

from cs2kit import bottle, cli, integrity, launch, recipe as recipe_mod
from cs2kit.util import EXIT_INTEGRITY, EXIT_NOT_READY, EXIT_OK, EXIT_USAGE


def largs(**kw):
    return argparse.Namespace(**{"profile": None, "prefix": None, "print_only": True,
                                 "force": False, "timeout": 5.0, "json": False, "extra": [], **kw})


def make_bottle_with_steam(sandbox):
    (sandbox.prefix / "system.reg").write_text("WINE REGISTRY")
    steam = sandbox.prefix / launch.STEAM_EXE
    steam.parent.mkdir(parents=True, exist_ok=True)
    steam.write_bytes(b"MZ")
    return steam


def test_launch_refuses_a_modified_binary(sandbox, cs2_tree, capsys):
    make_bottle_with_steam(sandbox)
    integrity.create_baseline()
    (cs2_tree / "engine2.dll").write_bytes(b"MZ-engine-PATCHED")
    assert launch.cmd_launch(largs()) == EXIT_INTEGRITY
    out = capsys.readouterr().out
    assert "REFUSING TO LAUNCH" in out and "Verify integrity" in out


def test_force_overrides_the_guard(sandbox, cs2_tree, capsys):
    make_bottle_with_steam(sandbox)
    integrity.create_baseline()
    (cs2_tree / "engine2.dll").write_bytes(b"MZ-engine-PATCHED")
    assert launch.cmd_launch(largs(force=True)) == EXIT_OK


def test_launch_without_a_bottle_or_steam_is_not_ready(sandbox, cs2_tree, capsys):
    integrity.create_baseline()
    assert launch.cmd_launch(largs()) == EXIT_NOT_READY
    (sandbox.prefix / "system.reg").write_text("WINE REGISTRY")
    assert launch.cmd_launch(largs()) == EXIT_NOT_READY
    assert "SteamSetup.exe" in capsys.readouterr().out


def test_command_is_a_plain_steam_applaunch(sandbox, cs2_tree):
    make_bottle_with_steam(sandbox)
    integrity.create_baseline()
    rec = recipe_mod.resolve("balanced-1080p")
    cmd = launch.build_command(rec, sandbox.prefix)
    assert cmd[-3:] == ["-novid", "-nojoy", "-console"]
    assert "-applaunch" in cmd and "730" in cmd
    env = launch.launch_env(rec, sandbox.prefix)
    assert env["WINEPREFIX"] == str(sandbox.prefix) and env["WINEMSYNC"] == "1"


def test_vulkan_is_refused_even_when_passed_by_hand(sandbox):
    with pytest.raises(recipe_mod.RecipeError) as exc:
        launch.build_command(None, sandbox.prefix, extra=["-vulkan"])
    assert "DX11" in str(exc.value)


def test_cli_dispatches_and_reports_version(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--version"])
    assert cli.main([]) == EXIT_USAGE


def test_every_command_is_registered_and_help_works(capsys):
    parser = cli.build_parser()
    actions = [a for a in parser._actions if a.dest == "command"]
    names = set(actions[0].choices)
    assert {"doctor", "bottle", "config", "verify", "launch", "env"} <= names
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    assert "configures and diagnoses" in capsys.readouterr().out


def test_a_broken_command_module_does_not_break_the_cli(monkeypatch, capsys):
    monkeypatch.setattr(cli, "COMMAND_MODULES", cli.COMMAND_MODULES + ["cs2kit.nonexistent"])
    parser = cli.build_parser()
    assert "nonexistent" in [a for a in parser._actions if a.dest == "command"][0].choices
    assert cli.main(["doctor", "--json"]) in (0, 1)


def test_env_snapshot_is_stable_across_two_runs(sandbox, cs2_tree):
    from cs2kit import probe
    first, second = probe.snapshot(), probe.snapshot()
    assert first["stable"] == second["stable"]     # T-005 acceptance
    assert first["env_id"] == second["env_id"]
    assert first["stable"]["cs2_buildid"] == "24828357"


def test_json_errors_have_one_machine_readable_shape(sandbox, capsys):
    """Documented caveat turned into a contract: --json failures are JSON."""
    import json as _json

    from cs2kit import bottle, config

    cases = [
        (bottle.cmd_diff, argparse.Namespace(recipe=None, prefix=str(sandbox.prefix / "nope"),
                                             json=True, dry_run=False), "bottle diff"),
        (config.cmd_apply, argparse.Namespace(profile="no-such-profile", no_cfg=True, video=False,
                                              dry_run=True, json=True), "config apply"),
        (launch.cmd_launch, largs(json=True, profile="no-such-profile"), "launch"),
    ]
    for func, ns, command in cases:
        assert func(ns) == EXIT_NOT_READY
        payload = _json.loads(capsys.readouterr().out)
        assert payload == {"command": command, "ok": False, "detail": payload["detail"]}
        assert payload["detail"]


def test_steam_exe_is_found_whatever_its_case(sandbox):
    """The installer writes Steam.exe; a case-sensitive APFS volume then makes a
    literal steam.exe lookup fail on a perfectly good bottle."""
    directory = sandbox.prefix / launch.STEAM_DIR
    directory.mkdir(parents=True)
    (directory / "Steam.exe").write_bytes(b"MZ")
    found = launch.steam_exe(sandbox.prefix)
    assert found is not None and found.name == "Steam.exe"
    assert launch.steam_exe(sandbox.root / "no-prefix") is None
