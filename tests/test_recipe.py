import pytest

from cs2kit import recipe as recipe_mod

GOOD = """
schema: 1
kind: bottle
name: t
wine:
  windows_version: win10
  dll_overrides: {}
  app_defaults:
    cs2.exe:
      windows_version: win8
dxmt:
  build: builtin
env:
  WINEMSYNC: 1
game:
  launch_options:
    - -novid
display:
  hidpi: false
"""


def test_shipped_bottle_recipe_is_valid(sandbox):
    rec = recipe_mod.load_default()
    assert rec.validate() == []
    assert rec.kind == "bottle"
    assert rec.app_defaults["cs2.exe"]["windows_version"] == "win8"   # the audio fix (T-009)
    assert "-vulkan" not in rec.launch_options
    # The published DXMT release is the builtin build: no overrides, ever.
    assert rec.dxmt_build == "builtin" and rec.dll_overrides == {}


@pytest.mark.parametrize("name", ["balanced-1080p", "competitive-lowest-latency", "thermal-limited"])
def test_shipped_profiles_are_valid_and_carry_provenance(sandbox, name):
    rec = recipe_mod.resolve(name)
    assert rec.validate() == [], rec.validate()
    assert rec.kind == "profile"
    assert rec.data["provenance"], "T-027 requires provenance naming the measuring task"


def test_overriding_a_builtin_dxmt_build_is_rejected():
    """DXMT's wiki: for the published builtin build these DLLs must NOT be
    overridden native - do it anyway and Wine silently loads something else."""
    bad = GOOD.replace("  dll_overrides: {}",
                       '  dll_overrides:\n    d3d11: "native,builtin"')
    problems = recipe_mod.loads(bad).validate()
    assert any("builtin" in p and "d3d11" in p for p in problems)
    worse = GOOD.replace("  WINEMSYNC: 1", '  WINEMSYNC: 1\n  WINEDLLOVERRIDES: "d3d11,dxgi=n,b"')
    assert any("WINEDLLOVERRIDES" in p for p in recipe_mod.loads(worse).validate())


def test_a_prefix_build_must_have_the_overrides_on():
    prefix_build = GOOD.replace("  build: builtin", "  build: prefix")
    problems = recipe_mod.loads(prefix_build).validate()
    assert any("d3d11" in p and "native" in p for p in problems)
    fixed = prefix_build.replace("  dll_overrides: {}",
                                 '  dll_overrides:\n    d3d11: "native,builtin"\n    dxgi: "native,builtin"')
    assert recipe_mod.loads(fixed).validate() == []


def test_unknown_dxmt_build_is_rejected():
    assert any("dxmt.build" in p
               for p in recipe_mod.loads(GOOD.replace("build: builtin", "build: magic")).validate())


def test_forbidden_launch_option_is_rejected():
    bad = GOOD.replace("    - -novid", "    - -novid\n    - -vulkan")
    assert any("-vulkan" in p for p in recipe_mod.loads(bad).validate())


def test_hidpi_and_double_sync_are_rejected():
    bad = GOOD.replace("hidpi: false", "hidpi: true").replace("WINEMSYNC: 1", "WINEMSYNC: 1\n  WINEESYNC: 1")
    problems = recipe_mod.loads(bad).validate()
    assert any("hidpi" in p for p in problems)
    assert any("mutually exclusive" in p for p in problems)


def test_require_valid_raises_with_source_name():
    with pytest.raises(recipe_mod.RecipeError):
        recipe_mod.loads(GOOD.replace("schema: 1", "schema: 99"), source="x.yaml").require_valid()


def test_hash_changes_with_content_and_diff_reports_the_field():
    a = recipe_mod.loads(GOOD)
    b = recipe_mod.loads(GOOD.replace("windows_version: win10", "windows_version: winxp"))
    assert a.hash() != b.hash()
    diff = a.diff(b)
    assert diff["wine.windows_version"] == {"expected": "win10", "actual": "winxp"}


def test_resolve_unknown_profile_lists_alternatives(sandbox):
    with pytest.raises(recipe_mod.RecipeError) as exc:
        recipe_mod.resolve("nope")
    assert "balanced-1080p" in str(exc.value)
