
"""Every checksum in this repo must trace to an artefact we actually measured.

Written after a near-miss on 2026-08-24: a search-and-replace updated only the
first four characters of a SHA-256 in docs/08, producing a digest that belonged
to nothing. A fabricated checksum is worse than no checksum - it looks verified.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Digests we have computed ourselves, with what they belong to. Adding a row
#: here is a deliberate act: it means someone ran `shasum -a 256` on the file.
KNOWN_DIGESTS = {
    "9da7ee0cbf386522f3a9906943726d9c3c125dbbd9ab120e3cde80e88d6091b2":
        "WS12WineSikarugir10.0_6.tar.xz - the engine of record",
    "9fa15479e7ff6abd99c1d07be285fb95f41fc6991586502427152b1f7d6ccb8a":
        "Template-1.0.11.tar.xz - the wrapper whose dylibs the engine needs",
    "8f260e36b5739e68f3bad613381441385c4dc7b85b78ba8de653d5a6a264529d":
        "dxmt-v0.80-builtin.tar.gz",
    "a8c50d0e14fb7982a21506287e1e41e1990fe77c74fa2a32da7dbcf7b21de1e2":
        "wine-staging-11.15-osx64.tar.xz - measured, then REJECTED (no Metal view)",
    "203f9e9fd6c2cc77e6525d798a434ced326145db34a356355e05659d3445fd1c":
        "WS12WineCX24.0.7_7.tar.xz - measured, then REJECTED (0x3008)",
    "7d3654531c32d941b8cae81c4137fc542172bfa9635f169cb392f245a0a12bcb":
        "SteamSetup.exe",
    "e24ba084737c8823e8439f7cb75d436a917fd92fc34b832bcaa0c0037eb33d03":
        "quoted from the deleted gcenx wine-crossover cask (historical record)",
}

SEARCHED = ["docs/**/*.md", "research/*.md", "*.md", "cs2kit/*.py", "profiles/*.yaml", "scripts/*"]
DIGEST = re.compile(r"\b[0-9a-f]{64}\b")


def files():
    for pattern in SEARCHED:
        for path in ROOT.glob(pattern):
            if path.is_file():
                yield path


def test_every_published_digest_is_one_we_measured():
    unknown = {}
    for path in files():
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for digest in DIGEST.findall(text):
            if digest not in KNOWN_DIGESTS:
                unknown.setdefault(digest, []).append(str(path.relative_to(ROOT)))
    assert not unknown, (
        "checksums that belong to no measured artefact (a truncated edit produces exactly this):\n"
        + "\n".join(f"  {d} in {', '.join(files_)}" for d, files_ in unknown.items()))


def test_the_engine_of_record_digest_is_the_one_the_code_installs():
    from cs2kit import engine

    recorded = engine.ENGINES[engine.RECOMMENDED].sha256
    assert recorded in KNOWN_DIGESTS, "cs2kit/engine.py ships a digest nobody measured"
    assert "engine of record" in KNOWN_DIGESTS[recorded]


def test_rejected_engines_keep_their_digests_and_their_reasons():
    from cs2kit import engine

    for name in ("gcenx-11", "crossover-24"):
        entry = engine.ENGINES[name]
        assert entry.verdict == "broken"
        assert entry.sha256 in KNOWN_DIGESTS
        assert "REJECTED" in KNOWN_DIGESTS[entry.sha256]
