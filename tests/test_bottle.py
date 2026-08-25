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


def test_desired_registry_sets_windows_versions_and_no_dxmt_overrides(sandbox):
    """The shipped recipe uses DXMT's builtin build, so the registry must carry
    the Windows versions and NOT a d3d11/dxgi override."""
    triples = bottle.desired_registry(rec(sandbox))
    flat = {(k.split("Wine")[-1], n): v for k, n, v in triples}
    assert flat[("", "Version")] == "win10"
    assert flat[(r"\AppDefaults\cs2.exe", "Version")] == "win8"
    assert not [key for key in flat if "DllOverrides" in key[0]]


def test_create_writes_state_and_registry(sandbox):
    runner = FakeRunner(sandbox.prefix)
    result = bottle.create(rec(sandbox), prefix=sandbox.prefix, runner=runner)
    assert ["wine", "wineboot", "--init"] == runner.log[0]
    state = bottle.read_state(sandbox.prefix)
    assert state["recipe_name"] == "cs2-default"
    assert state["recipe_hash"] == rec(sandbox).hash()
    assert runner.registry[(bottle.WINE_KEY, "Version")] == "win10"


def test_create_refuses_an_invalid_recipe(sandbox):
    bad = recipe_mod.loads("schema: 1\nkind: bottle\nname: bad\ndxmt:\n  build: prefix\n")
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

    runner.registry[(bottle.WINE_KEY + r"\AppDefaults\cs2.exe", "Version")] = "win10"
    drift = bottle.diff(recipe, sandbox.prefix, runner)
    assert r"Wine\AppDefaults\cs2.exe\Version" in drift        # the audio fix was lost
    assert drift[r"Wine\AppDefaults\cs2.exe\Version"]["actual"] == "win10"

    result = bottle.repair(recipe, sandbox.prefix, runner)
    assert result["fixed"] == [r"Wine\AppDefaults\cs2.exe\Version"]
    assert bottle.diff(recipe, sandbox.prefix, runner) == {}


def fake_release(tmp_path):
    """The layout of a real dxmt-vX-builtin.tar.gz."""
    source = tmp_path / "dxmt"
    (source / "x86_64-unix").mkdir(parents=True)
    (source / "x86_64-windows").mkdir(parents=True)
    (source / "i386-windows").mkdir(parents=True)
    (source / "x86_64-unix" / "winemetal.so").write_bytes(b"so")
    for name in ("winemetal.dll", "d3d11.dll", "dxgi.dll", "d3d10core.dll"):
        (source / "x86_64-windows" / name).write_bytes(b"dll64")
        (source / "i386-windows" / name).write_bytes(b"dll32")
    return source


def fake_wine(tmp_path):
    root = tmp_path / "wine"
    for abi in ("x86_64-unix", "x86_64-windows", "i386-windows"):
        (root / "lib" / "wine" / abi).mkdir(parents=True)
    (root / "bin").mkdir()
    return root


def test_install_dxmt_rejects_a_directory_that_is_not_a_release(sandbox, tmp_path):
    source = tmp_path / "dxmt"
    (source / "x64").mkdir(parents=True)
    (source / "x64" / "d3d11.dll").write_bytes(b"dll")
    with pytest.raises(bottle.BottleError) as exc:
        bottle.install_dxmt(rec(sandbox), source, sandbox.prefix, wine=fake_wine(tmp_path))
    assert "x86_64-unix" in str(exc.value)


def test_builtin_build_installs_into_the_wine_tree(sandbox, tmp_path):
    """The published release is the builtin build: the DLLs belong to Wine, and
    only winemetal.dll is additionally placed in the prefix (DXMT wiki)."""
    source, wine = fake_release(tmp_path), fake_wine(tmp_path)
    copied = bottle.install_dxmt(rec(sandbox), source, sandbox.prefix, wine=wine)
    assert (wine / "lib" / "wine" / "x86_64-unix" / "winemetal.so").is_file()
    assert (wine / "lib" / "wine" / "x86_64-windows" / "d3d11.dll").is_file()
    assert (wine / "lib" / "wine" / "i386-windows" / "dxgi.dll").is_file()
    system32 = sandbox.prefix / "drive_c" / "windows" / "system32"
    assert (system32 / "winemetal.dll").is_file()
    assert not (system32 / "d3d11.dll").exists()   # would shadow the builtin
    assert len(copied) == 10


def test_builtin_build_without_a_wine_tree_is_an_error(sandbox, tmp_path, monkeypatch):
    monkeypatch.setattr(bottle, "which", lambda name: None)
    with pytest.raises(bottle.BottleError) as exc:
        bottle.install_dxmt(rec(sandbox), fake_release(tmp_path), sandbox.prefix)
    assert "--wine-root" in str(exc.value)


def test_prefix_build_installs_into_system32(sandbox, tmp_path):
    source, wine = fake_release(tmp_path), fake_wine(tmp_path)
    prefix_recipe = recipe_mod.loads(
        rec(sandbox).dumps().replace("build: builtin", "build: prefix").replace(
            "  dll_overrides: {}", '  dll_overrides:\n    d3d11: "native,builtin"\n'
                                   '    dxgi: "native,builtin"'))
    bottle.install_dxmt(prefix_recipe, source, sandbox.prefix, wine=wine)
    system32 = sandbox.prefix / "drive_c" / "windows" / "system32"
    syswow64 = sandbox.prefix / "drive_c" / "windows" / "syswow64"
    assert (system32 / "d3d11.dll").is_file() and (syswow64 / "dxgi.dll").is_file()
    # winemetal.so can only be loaded by Wine's unix side, so it stays in the tree
    assert (wine / "lib" / "wine" / "x86_64-unix" / "winemetal.so").is_file()


def test_wine_root_resolution_order(sandbox, tmp_path, monkeypatch):
    """The launcher app runs without the engine on PATH, so `which wine` cannot be
    the only source - the bottle records what it was built with."""
    root = fake_wine(tmp_path)
    (root / "bin" / "wine").write_text("#!/bin/sh\n")

    monkeypatch.setattr(bottle, "which", lambda name: None)
    assert bottle.wine_root() is None                      # nothing known yet

    monkeypatch.setattr(bottle, "which", lambda name: str(root / "bin" / "wine"))
    assert bottle.wine_root() == root                      # from PATH

    recorded = fake_wine(tmp_path / "recorded")
    from cs2kit.util import write_json
    write_json(bottle.state_file(sandbox.prefix), {"wine_root": str(recorded)})
    assert bottle.wine_root() == recorded                  # the bottle wins over PATH

    assert bottle.wine_root(str(root)) == root             # explicit wins over both
    assert bottle.wine_root(str(tmp_path / "nope")) is None


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


def test_link_library_maps_a_drive_and_refuses_nonsense(sandbox, tmp_path):
    (sandbox.prefix / "dosdevices").mkdir(parents=True)
    (sandbox.steam / "steamapps").mkdir(exist_ok=True)
    result = bottle.link_library(sandbox.prefix, sandbox.steam, "s")
    link = sandbox.prefix / "dosdevices" / "s:"
    assert link.is_symlink() and link.resolve() == sandbox.steam.resolve()
    assert result["steamapps"] == "S:\\steamapps"

    # re-mapping is idempotent, not an error
    bottle.link_library(sandbox.prefix, sandbox.steam, "s")

    for bad_letter in ("c", "zz", "1"):
        with pytest.raises(bottle.BottleError):
            bottle.link_library(sandbox.prefix, sandbox.steam, bad_letter)
    with pytest.raises(bottle.BottleError):
        bottle.link_library(sandbox.prefix, tmp_path / "nope", "t")
    plain = tmp_path / "not-a-library"
    plain.mkdir()
    with pytest.raises(bottle.BottleError) as exc:
        bottle.link_library(sandbox.prefix, plain, "t")
    assert "steamapps" in str(exc.value)


def test_dxmt_install_backs_up_the_wine_dlls_it_replaces(sandbox, tmp_path):
    """Without a backup, "is DXMT the problem?" needs a fresh Wine download."""
    source, wine = fake_release(tmp_path), fake_wine(tmp_path)
    original = wine / "lib" / "wine" / "x86_64-windows" / "d3d11.dll"
    original.write_bytes(b"WINE-OWN-D3D11")

    bottle.install_dxmt(rec(sandbox), source, sandbox.prefix, wine=wine)
    assert original.read_bytes() == b"dll64"                      # DXMT is in place
    slot = wine / bottle.BACKUP_DIR / "x86_64-windows" / "d3d11.dll"
    assert slot.read_bytes() == b"WINE-OWN-D3D11"                 # Wine's own is safe

    # a second install must not overwrite the backup with DXMT's own copy
    bottle.install_dxmt(rec(sandbox), source, sandbox.prefix, wine=wine)
    assert slot.read_bytes() == b"WINE-OWN-D3D11"

    restored = bottle.restore_wine_dlls(wine)
    assert original.read_bytes() == b"WINE-OWN-D3D11"
    assert str(original) in restored


def test_restore_without_a_backup_explains_itself(sandbox, tmp_path):
    with pytest.raises(bottle.BottleError) as exc:
        bottle.restore_wine_dlls(fake_wine(tmp_path))
    assert "re-extract the Wine tarball" in str(exc.value)


def test_link_steamapps_refuses_the_macos_library_by_default(sandbox):
    (sandbox.prefix / "drive_c" / "Program Files (x86)" / "Steam").mkdir(parents=True)
    (sandbox.steam / "steamapps" / "common").mkdir(parents=True, exist_ok=True)
    with pytest.raises(bottle.BottleError) as exc:
        bottle.link_steamapps(sandbox.prefix, sandbox.steam / "steamapps")
    assert "macOS Steam will delete" in str(exc.value)
    # explicit opt-in still works, for someone who knows what they are doing
    bottle.link_steamapps(sandbox.prefix, sandbox.steam / "steamapps", allow_macos_library=True)


def test_link_steamapps_defaults_to_a_bottle_only_library(sandbox, monkeypatch, tmp_path):
    monkeypatch.setenv("CS2KIT_LIBRARY", str(tmp_path / "lib"))
    (sandbox.prefix / "drive_c" / "Program Files (x86)" / "Steam").mkdir(parents=True)
    result = bottle.link_steamapps(sandbox.prefix)
    assert result["target"] == str(tmp_path / "lib" / "steamapps")
    assert (tmp_path / "lib" / "steamapps" / "libraryfolder.vdf").is_file()


def test_migrate_moves_the_game_and_its_manifest_out(sandbox, monkeypatch, tmp_path):
    monkeypatch.setenv("CS2KIT_LIBRARY", str(tmp_path / "lib"))
    game = sandbox.steam / "steamapps" / "common" / "Counter-Strike Global Offensive"
    (game / "game").mkdir(parents=True)
    (sandbox.steam / "steamapps" / "appmanifest_730.acf").write_text('"AppState" { }')
    result = bottle.migrate_macos_install()
    assert len(result["moved"]) == 2
    assert (tmp_path / "lib" / "steamapps" / "common" / game.name / "game").is_dir()
    assert not game.exists()
    assert not (sandbox.steam / "steamapps" / "appmanifest_730.acf").exists()
    # idempotent: a second run finds nothing to do
    assert bottle.migrate_macos_install()["moved"] == []
