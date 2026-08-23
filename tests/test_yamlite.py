import pytest

from cs2kit import yamlite


def test_nested_mapping_and_typed_scalars():
    doc = yamlite.loads("""
        schema: 1
        name: cs2-default
        wine:
          windows_version: win10
          dll_overrides:
            d3d11: "native,builtin"
        env:
          WINEMSYNC: 1
          WINEDEBUG: "-all"
        display:
          hidpi: false
          note: null
    """)
    assert doc["schema"] == 1
    assert doc["wine"]["dll_overrides"]["d3d11"] == "native,builtin"
    assert doc["env"]["WINEMSYNC"] == 1 and doc["env"]["WINEDEBUG"] == "-all"
    assert doc["display"]["hidpi"] is False and doc["display"]["note"] is None


def test_sequences_of_scalars_and_mappings():
    doc = yamlite.loads("""
        launch_options:
          - -novid
          - -nojoy
        overrides:
          - name: d3d11
            mode: native
          - name: dxgi
            mode: builtin
        inline: [a, b, c]
    """)
    assert doc["launch_options"] == ["-novid", "-nojoy"]
    assert doc["overrides"][1] == {"name": "dxgi", "mode": "builtin"}
    assert doc["inline"] == ["a", "b", "c"]


def test_comments_are_stripped_but_not_inside_quotes():
    doc = yamlite.loads('a: 1  # trailing\nb: "has # hash"\n')
    assert doc == {"a": 1, "b": "has # hash"}


def test_roundtrip_is_stable():
    original = {"name": "x", "n": 3, "on": True, "off": False, "nothing": None,
                "list": [1, "two"], "nested": {"k": "v: with colon"}, "empty": {}}
    assert yamlite.loads(yamlite.dumps(original)) == original


def test_numeric_looking_strings_stay_strings_after_roundtrip():
    assert yamlite.loads(yamlite.dumps({"v": "011"}))["v"] == "011"


def test_tabs_and_garbage_raise():
    with pytest.raises(yamlite.YamlError):
        yamlite.loads("a:\n\tb: 1\n")
    with pytest.raises(yamlite.YamlError):
        yamlite.loads("just a bare line\n")
