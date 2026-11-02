import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Avoid pytest's predictable shared temporary root (CVE-2025-71176).

    Python 3.9's last compatible pytest is unfixed. Configure a fresh private
    parent before pytest's TempPathFactory is initialized, on every version.
    """
    temporary = tempfile.TemporaryDirectory(prefix="cs2kit-tests-")
    config._cs2kit_private_temp = temporary
    config.option.basetemp = str(Path(temporary.name) / "data")


def pytest_unconfigure(config):
    temporary = getattr(config, "_cs2kit_private_temp", None)
    if temporary:
        temporary.cleanup()


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
    # The game can live in a bottle-only library; tests must never see the real one.
    monkeypatch.setenv("CS2KIT_LIBRARY", str(tmp_path / "cs2-library"))
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
