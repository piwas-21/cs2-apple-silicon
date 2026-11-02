import argparse
from pathlib import Path

from cs2kit import config, recipe as recipe_mod
from cs2kit.util import EXIT_NOT_READY, EXIT_OK, PASS, WARN


def apply_args(profile, **kw):
    return argparse.Namespace(**{"profile": profile, "no_cfg": False, "video": False,
                                 "video_path": None, "dry_run": False, "json": False, **kw})


def test_apply_writes_a_sourceable_env_script(sandbox):
    result = config.apply(recipe_mod.resolve("balanced-1080p"))
    script = open(result["record"]["env_script"]).read()
    assert script.startswith("#!/usr/bin/env bash")
    assert 'export WINEMSYNC=1' in script
    assert str(sandbox.prefix) in script
    assert config.active()["name"] == "balanced-1080p"


def test_env_script_expands_dollar_home_before_quoting(sandbox):
    # Inside shlex's single quotes a literal $HOME would survive sourcing, and
    # `mkdir -p "$DXMT_SHADER_CACHE"` would create a directory named '$HOME'.
    # The value must be expanded at render time, the way `play` expands it.
    rec = recipe_mod.loads(
        'schema: 1\nname: homey\nkind: profile\nprovenance: measured\n'
        'env:\n  DXMT_SHADER_CACHE: "$HOME/.cs2kit/shader-cache"\n'
        'display:\n  width: 1920\n  height: 1080\n')
    rec.require_valid()
    result = config.apply(rec)
    script = open(result["record"]["env_script"]).read()
    assert f"export DXMT_SHADER_CACHE={Path.home()}/.cs2kit/shader-cache" in script
    assert "$HOME" not in script


def test_apply_writes_the_game_cfg_only_when_cs2_is_installed(sandbox, cs2_tree):
    cfg_dir = cs2_tree.parent.parent / "csgo" / "cfg"   # <install>/game/csgo/cfg
    cfg_dir.mkdir(parents=True)
    result = config.apply(recipe_mod.resolve("competitive-lowest-latency"), write_video=True)
    cfg = (cfg_dir / config.CFG_NAME).read_text()
    assert 'm_rawinput "1"' in cfg and "provenance" in cfg
    video = (cfg_dir / "CS2Video.txt").read_text()
    assert '"setting.defaultres"\t\t"1280"' in video
    assert '"setting.fullscreen"\t\t"1"' in video
    assert result["record"]["cfg"].endswith(config.CFG_NAME)


def test_apply_without_cs2_still_succeeds(sandbox, capsys):
    assert config.cmd_apply(apply_args("thermal-limited")) == EXIT_OK
    assert "CS2 is not installed yet" in capsys.readouterr().out


def test_dry_run_writes_nothing(sandbox):
    result = config.apply(recipe_mod.resolve("balanced-1080p"), dry_run=True)
    assert not config.active_path().exists()
    assert not config.env_script_path("balanced-1080p").exists()
    assert result["dry_run"]


def test_active_check_tracks_profile_edits(sandbox, tmp_path, monkeypatch):
    assert config.active_check().status == WARN            # nothing applied
    config.apply(recipe_mod.resolve("balanced-1080p"))
    assert config.active_check().status == PASS
    record = config.active()
    record["hash"] = "stale"
    config.active_path().write_text(__import__("json").dumps(record))
    check = config.active_check()
    assert check.status == WARN and "changed since" in check.detail


def test_unknown_profile_is_not_ready(sandbox):
    assert config.cmd_apply(apply_args("does-not-exist")) == EXIT_NOT_READY


def test_list_marks_the_active_profile(sandbox, capsys):
    config.apply(recipe_mod.resolve("thermal-limited"))
    config.cmd_list(argparse.Namespace(json=False))
    out = capsys.readouterr().out
    assert " * thermal-limited" in out
    assert "INVALID" not in out


def test_video_txt_carries_the_unconfirmed_path_caveat(sandbox, cs2_tree, capsys):
    cfg_dir = cs2_tree.parent.parent / "csgo" / "cfg"
    cfg_dir.mkdir(parents=True)
    assert config.cmd_apply(apply_args("balanced-1080p", video=True, video_path=None)) == EXIT_OK
    assert "UNCONFIRMED" in capsys.readouterr().out


def test_video_path_override(sandbox, tmp_path):
    target = tmp_path / "userdata" / "CS2Video.txt"
    result = config.apply(recipe_mod.resolve("balanced-1080p"), write_video=True, video_path=target)
    assert result["record"]["video_txt"] == str(target)
    assert "setting.fullscreen" in target.read_text()
