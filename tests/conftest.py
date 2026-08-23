import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """An isolated CS2Kit world: fake Steam root, fake prefix, fake state dir.

    Tests must never touch the real ~/Library/Application Support/Steam or the
    real WINEPREFIX, so every path CS2Kit resolves is redirected here.
    """
    steam = tmp_path / "Steam"
    prefix = tmp_path / "prefix"
    home = tmp_path / "cs2kit-home"
    (steam / "steamapps" / "common").mkdir(parents=True)
    prefix.mkdir(parents=True)
    home.mkdir(parents=True)
    monkeypatch.setenv("CS2KIT_STEAM", str(steam))
    monkeypatch.setenv("CS2KIT_HOME", str(home))
    monkeypatch.setenv("CS2KIT_REPO", str(ROOT))
    monkeypatch.setenv("WINEPREFIX", str(prefix))
    monkeypatch.setenv("CS2KIT_NO_COLOR", "1")
    return type("Sandbox", (), {"root": tmp_path, "steam": steam,
                                "prefix": prefix, "home": home})


@pytest.fixture()
def cs2_tree(sandbox):
    """A minimal but realistic installed-CS2 tree with a win64 binary set."""
    game = sandbox.steam / "steamapps" / "common" / "Counter-Strike Global Offensive"
    win64 = game / "game" / "bin" / "win64"
    win64.mkdir(parents=True)
    for name, body in (("cs2.exe", b"MZ-cs2"), ("engine2.dll", b"MZ-engine"),
                       ("client.dll", b"MZ-client"), ("tier0.dll", b"MZ-tier0")):
        (win64 / name).write_bytes(body)
    (sandbox.steam / "steamapps" / "appmanifest_730.acf").write_text(
        '''"AppState"
{
\t"appid"\t\t"730"
\t"name"\t\t"Counter-Strike 2"
\t"installdir"\t\t"Counter-Strike Global Offensive"
\t"buildid"\t\t"24828357"
\t"InstalledDepots"
\t{
\t\t"2347770"\t\t{ "manifest"\t\t"1" }
\t\t"2347771"\t\t{ "manifest"\t\t"2" }
\t}
}
''')
    return win64
