"""Issue #3, slice 1: discovery must be useful and incapable of changing state."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from cs2kit import cli, engine, setup


def parse_json(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def tree_snapshot(root: Path):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def fake_install(sandbox, monkeypatch, with_userdata=False, corrupt_record=False):
    """Build a complete-looking install entirely inside the sandbox."""
    setup_home = sandbox.root / "my cs2 setup"
    state_home = sandbox.root / "state home"
    prefix = setup_home / "prefix"
    steam_dir = prefix / "drive_c" / "Program Files (x86)" / "Steam"
    library = setup_home / "library"
    link_target = library / "steamapps"
    engine_root = state_home / "engines" / "sikarugir-10"
    wine_root = engine_root / "wswine.bundle"
    app = setup_home / "CS2Kit.app"

    link_target.mkdir(parents=True)
    (link_target / "appmanifest_730.acf").write_text('"AppState"\n{\n}\n')
    steam_dir.mkdir(parents=True)
    (prefix / "system.reg").write_text("")
    (steam_dir / "steamapps").symlink_to(link_target, target_is_directory=True)
    if with_userdata:
        (steam_dir / "userdata").mkdir()
    (prefix / "dosdevices").mkdir()
    (prefix / "dosdevices" / "c:").symlink_to(prefix / "drive_c", target_is_directory=True)
    (prefix / ".cs2kit").mkdir()
    record = {"recipe_name": "bottle", "created": "2026-11-19T00:00:00Z",
              "wine_root": str(wine_root)}
    (prefix / ".cs2kit" / "state.json").write_text(
        "not json" if corrupt_record else json.dumps(record))

    (wine_root / "bin").mkdir(parents=True)
    (wine_root / "bin" / "wine").write_text("")
    (engine_root / "cs2kit-engine.json").write_text(
        json.dumps({"engine": "sikarugir-10", "version": "wine-10.0"}))
    engine_archive = state_home / "engines" / Path(engine.ENGINES["sikarugir-10"].url).name
    engine_archive.write_text("")

    dxmt = setup_home / "dxmt" / "v0.80" / "x86_64-unix"
    dxmt.mkdir(parents=True)
    (dxmt / "winemetal.so").write_text("")
    downloads = setup_home / "downloads"
    downloads.mkdir()
    (downloads / "SteamSetup.exe").write_text("")
    (downloads / Path(setup.DXMT_RELEASE["url"]).name).write_text("")
    (setup_home / "cs2kit-app.log").write_text("")

    runtime = state_home / "runtime"
    (runtime / "bin").mkdir(parents=True)
    (runtime / "bin" / "cs2kit").write_text("")
    (runtime / "cs2kit").mkdir()
    (runtime / "cs2kit" / "__init__.py").write_text("")
    (state_home / "shader-cache").mkdir(parents=True)
    (state_home / "env").mkdir()
    (state_home / "env" / "balanced.sh").write_text("")
    cfg = link_target / "common" / "Counter-Strike Global Offensive" / "cs2kit.cfg"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("")
    (state_home / "active-profile.json").write_text(json.dumps({
        "name": "balanced-1080p", "env_script": str(state_home / "env" / "balanced.sh"),
        "cfg": str(cfg), "video_txt": None}))

    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "Info.plist").write_text("<string>org.cs2kit.CS2Kit</string>")

    for name, value in (("CS2KIT_SETUP_HOME", setup_home), ("CS2KIT_HOME", state_home),
                        ("WINEPREFIX", prefix), ("CS2KIT_LIBRARY", library)):
        monkeypatch.setenv(name, str(value))
    return type("Fake", (), {"setup": setup_home, "state": state_home, "prefix": prefix,
                             "library": library, "target": link_target, "app": app,
                             "wine_root": wine_root})


def inventory_argv(fake):
    return ["uninstall", "--prefix", str(fake.prefix), "--app-dest", str(fake.app)]


def group(plan, name):
    return {item["id"]: item for item in plan["groups"][name]}


def paths(plan, name):
    return {item["path"] for item in plan["groups"][name]}


def test_default_json_and_dry_run_are_pure_reads(sandbox, monkeypatch, capsys):
    state = sandbox.root / "must not exist" / "state"
    monkeypatch.setenv("CS2KIT_HOME", str(state))
    monkeypatch.setenv("CS2KIT_SETUP_HOME", str(sandbox.root / "must not exist" / "setup"))

    def forbidden(*args, **kwargs):
        pytest.fail("a read-only inventory must not start a process")

    monkeypatch.setattr(subprocess, "run", forbidden)
    before = tree_snapshot(sandbox.root)
    assert cli.main(["uninstall"]) == 0
    capsys.readouterr()
    assert cli.main(["uninstall", "--dry-run"]) == 0
    capsys.readouterr()
    assert cli.main(["uninstall", "--json"]) == 0
    plan = parse_json(capsys)
    assert tree_snapshot(sandbox.root) == before
    assert not state.exists()
    assert plan["read_only"] is True
    assert plan["apply_available"] is False
    assert plan["complete"] is False


def test_inventory_marks_owned_components_and_keeps_game_data(sandbox, monkeypatch, capsys):
    fake = fake_install(sandbox, monkeypatch)
    assert cli.main(inventory_argv(fake) + ["--json"]) == 0
    plan = parse_json(capsys)
    candidates, retained = group(plan, "candidate"), group(plan, "retain")

    assert any(key.startswith("prefix:") for key in candidates)
    assert any(key.startswith("engine:") for key in candidates)
    assert any(key.startswith("dxmt:") for key in candidates)
    assert any(key.startswith("runtime:") for key in candidates)
    assert any(key.startswith("launcher:") for key in candidates)
    assert any(key.startswith("download:") for key in candidates)
    assert str(fake.library) in paths(plan, "retain")
    assert str(fake.target) in paths(plan, "retain")
    assert str(fake.target / "appmanifest_730.acf") not in paths(plan, "candidate")
    assert not (paths(plan, "candidate") & paths(plan, "retain"))

    link_id = "link:" + str(fake.prefix / "drive_c" / "Program Files (x86)" / "Steam" / "steamapps")
    assert link_id in candidates
    assert candidates[link_id]["target"] == str(fake.target)
    assert str(fake.app) in paths(plan, "candidate")
    assert any(item["component"] == "Source checkout" for item in plan["groups"]["retain"])
    assert plan["counts"]["candidate"] > 0


def test_userdata_inside_prefix_forces_review(sandbox, monkeypatch, capsys):
    fake = fake_install(sandbox, monkeypatch, with_userdata=True)
    assert cli.main(inventory_argv(fake) + ["--json"]) == 0
    plan = parse_json(capsys)
    prefix = next(i for i in plan["groups"]["review"] if i["id"].startswith("prefix:"))
    assert "userdata" in prefix["reason"]
    userdata = fake.prefix / "drive_c" / "Program Files (x86)" / "Steam" / "userdata"
    assert str(userdata) in paths(plan, "retain")


def test_corrupt_record_is_review_not_a_removal_candidate(sandbox, monkeypatch, capsys):
    fake = fake_install(sandbox, monkeypatch, corrupt_record=True)
    assert cli.main(inventory_argv(fake) + ["--json"]) == 0
    plan = parse_json(capsys)
    assert not any(i["id"].startswith("prefix:") for i in plan["groups"]["candidate"])
    prefix = next(i for i in plan["groups"]["review"] if i["id"].startswith("prefix:"))
    assert prefix["ownership"] == "ambiguous"


def test_multiple_prefixes_are_inspected(sandbox, monkeypatch, capsys):
    first = fake_install(sandbox, monkeypatch)
    second = first.setup / "second prefix"
    (second / ".cs2kit").mkdir(parents=True)
    (second / "system.reg").write_text("")
    (second / ".cs2kit" / "state.json").write_text("{}")
    assert cli.main(["uninstall", "--json", "--prefix", str(first.prefix),
                     "--prefix", str(second)]) == 0
    plan = parse_json(capsys)
    prefix_ids = {i["path"] for group_name in ("candidate", "review")
                  for i in plan["groups"][group_name] if i["id"].startswith("prefix:")}
    assert str(first.prefix) in prefix_ids
    assert str(second) in prefix_ids


def test_apply_is_refused_without_touching_anything(sandbox, monkeypatch, capsys):
    fake = fake_install(sandbox, monkeypatch)
    before = tree_snapshot(sandbox.root)
    assert cli.main(inventory_argv(fake) + ["--apply"]) == 2
    out = capsys.readouterr().out
    assert "not implemented" in out
    assert tree_snapshot(sandbox.root) == before
    assert cli.main(["uninstall", "--apply", "--json"]) == 2
    error = parse_json(capsys)
    assert error["command"] == "uninstall --apply"
    assert error["ok"] is False


def test_filesystem_and_home_roots_are_refused(sandbox, monkeypatch, capsys):
    monkeypatch.setenv("CS2KIT_SETUP_HOME", str(sandbox.root / "setup"))
    assert cli.main(["uninstall", "--json", "--prefix", "/"]) == 0
    plan = parse_json(capsys)
    assert any(i["proposal"] == "refused" and i["path"] == "/"
               for i in plan["groups"]["refused"])
    assert not any(i["path"] == "/" for i in plan["groups"]["candidate"])


def test_paths_with_spaces_are_reported_verbatim(sandbox, monkeypatch, capsys):
    fake = fake_install(sandbox, monkeypatch)
    assert cli.main(inventory_argv(fake) + ["--json"]) == 0
    plan = parse_json(capsys)
    assert str(fake.setup) == plan["roots"]["setup_home"]
    assert str(fake.wine_root) in json.dumps(plan)
