import pytest

from cs2kit import recipe as recipe_mod

GOOD = """
schema: 1
kind: bottle
name: t
wine:
  windows_version: win10
  dll_overrides:
    d3d11: "native,builtin"
    dxgi: "native,builtin"
  app_defaults:
    cs2.exe:
      windows_version: win8
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


@pytest.mark.parametrize("name", ["balanced-1080p", "competitive-lowest-latency", "thermal-limited"])
def test_shipped_profiles_are_valid_and_carry_provenance(sandbox, name):
    rec = recipe_mod.resolve(name)
    assert rec.validate() == [], rec.validate()
    assert rec.kind == "profile"
    assert rec.data["provenance"], "T-027 requires provenance naming the measuring task"


def test_builtin_override_is_rejected():
    bad = GOOD.replace('d3d11: "native,builtin"', 'd3d11: builtin')
    problems = recipe_mod.loads(bad).validate()
    assert any("d3d11" in p for p in problems)


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
