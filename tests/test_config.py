import argparse

import pytest

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


def account_video(sandbox, account="123"):
    steam = sandbox.prefix / "drive_c" / "Program Files (x86)" / "Steam"
    steam.mkdir(parents=True, exist_ok=True)
    (steam / "steam.exe").write_bytes(b"MZ")
    target = steam / "userdata" / account / "730" / "local" / "cfg" / "cs2_video.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('"video.cfg"\n{\n"setting.defaultres" "-1"\n'
                      '"setting.defaultresheight" "-1"\n"setting.fullscreen" "1"\n'
                      '"setting.msaa_samples" "2"\n}\n')
    return target


def test_video_repair_finds_account_and_preserves_quality_and_backup(sandbox):
    target = account_video(sandbox)
    before = target.read_bytes()
    rec = recipe_mod.resolve("balanced-1080p")
    result = config.apply(rec, write_video=True)
    assert result["record"]["video_txt"] == str(target)
    assert '"setting.defaultres" "1920"' in target.read_text()
    assert '"setting.defaultresheight" "1080"' in target.read_text()
    assert '"setting.fullscreen" "0"' in target.read_text()
    assert '"setting.msaa_samples" "2"' in target.read_text()
    backup = target.with_name(target.name + ".cs2kit-backup")
    assert backup.read_bytes() == before
    config.apply(rec, write_video=True)
    assert backup.read_bytes() == before


def test_account_video_dry_run_preserves_original(sandbox):
    target = account_video(sandbox)
    before = target.read_bytes()
    result = config.apply(recipe_mod.resolve("balanced-1080p"), write_video=True, dry_run=True)
    assert result["record"]["video_txt"] == str(target)
    assert target.read_bytes() == before
    assert not target.with_name(target.name + ".cs2kit-backup").exists()


def test_multiple_accounts_require_explicit_video_path_before_writing(sandbox):
    target = account_video(sandbox)
    other = account_video(sandbox, "456")
    before = other.read_bytes()
    rec = recipe_mod.resolve("balanced-1080p")
    with pytest.raises(recipe_mod.RecipeError, match="multiple Steam accounts"):
        config.apply(rec, write_video=True)
    assert not config.active_path().exists()
    config.apply(rec, write_video=True, video_path=target)
    assert other.read_bytes() == before


def test_video_repair_preserves_comments_strings_and_nested_quality_settings(sandbox):
    target = account_video(sandbox)
    original = '''// "setting.defaultres" "640"
"video.cfg"
{
    /* old display settings: } "setting.fullscreen" "1" */
    "setting.defaultresheight" "-1" // keep this comment
    "quality" { "setting.defaultres" "777" }
    "description" "quoted } and \\"escaped quote\\""
    "setting.msaa_samples" "8"
}
// previous closing brace }
'''
    target.write_text(original)
    config.apply(recipe_mod.resolve("balanced-1080p"), write_video=True)
    repaired = target.read_text()
    assert '// "setting.defaultres" "640"' in repaired
    assert '/* old display settings: } "setting.fullscreen" "1" */' in repaired
    assert '"setting.defaultresheight" "1080" // keep this comment' in repaired
    assert '"quality" { "setting.defaultres" "777" }' in repaired
    assert '"description" "quoted } and \\"escaped quote\\""' in repaired
    assert '"setting.msaa_samples" "8"' in repaired
    assert repaired.endswith('}\n// previous closing brace }\n')
    # Parse after removing comments to check actual root values, not comment text.
    clean = repaired.replace('// "setting.defaultres" "640"', '').replace(
        '/* old display settings: } "setting.fullscreen" "1" */', '').replace(
        '// previous closing brace }', '')
    from cs2kit import probe
    values = probe.parse_acf(clean)
    assert values["setting.defaultres"] == "1920"
    assert values["setting.fullscreen"] == "0"
    assert values["setting.coop_fullscreen"] == "0"
    assert target.with_name(target.name + ".cs2kit-backup").read_text() == original
    assert config.update_video_txt(recipe_mod.resolve("balanced-1080p"), repaired) == repaired


@pytest.mark.parametrize("original", [
    '', 'garbage }', '"video.cfg" {', '"video.cfg" { "setting.fullscreen" }',
    '"video.cfg" { "unterminated "0" }', '"video.cfg" {} "other" {}',
    '"video.cfg" {} /*', '"video.cfg" { "nested" { "key" "value" }',
    '"video.cfg" { { "a" "b" } }', '"video.cfg" { "only_key"',
])
def test_invalid_video_config_is_rejected_before_any_write(sandbox, original):
    target = account_video(sandbox)
    target.write_text(original)
    rec = recipe_mod.resolve("balanced-1080p")
    with pytest.raises(recipe_mod.RecipeError, match="invalid video settings"):
        config.apply(rec, write_video=True)
    assert target.read_text() == original
    assert not target.with_name(target.name + ".cs2kit-backup").exists()
    assert not config.active_path().exists()
    assert not config.env_script_path(rec.name).exists()


def test_video_repair_updates_duplicate_active_keys_and_keeps_crlf(sandbox):
    original = ('\ufeff"video.cfg"\r\n{\r\n"setting.defaultres" "-1"\r\n'
                '"SETTING.DEFAULTRES" "800"\r\n}\r\n')
    repaired = config.update_video_txt(recipe_mod.resolve("balanced-1080p"), original)
    assert '"setting.defaultres" "1920"' in repaired
    assert '"SETTING.DEFAULTRES" "1920"' in repaired
    assert repaired.startswith('\ufeff"video.cfg"\r\n')
    assert '\n' not in repaired.replace('\r\n', '')
    target = account_video(sandbox)
    target.write_bytes(original.encode("utf-8"))
    config.apply(recipe_mod.resolve("balanced-1080p"), write_video=True)
    assert target.read_bytes() == repaired.encode("utf-8")
    assert target.with_name(target.name + ".cs2kit-backup").read_bytes() == original.encode("utf-8")


def test_video_repair_rejects_excessive_nesting(sandbox):
    original = '"video.cfg" {' + '"nested" {' * 64 + '}' * 65
    with pytest.raises(recipe_mod.RecipeError, match="invalid video settings"):
        config.update_video_txt(recipe_mod.resolve("balanced-1080p"), original)
