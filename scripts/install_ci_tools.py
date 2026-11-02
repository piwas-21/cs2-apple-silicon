"""Install one pinned CI binary after checksum verification; never extract paths."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path


def install(name: str, destination: Path) -> Path:
    pins = json.loads((Path(__file__).resolve().parent.parent / ".github/ci-tools.json").read_text())
    pin = pins[name]
    with tempfile.TemporaryDirectory(prefix="cs2kit-ci-tool-") as temporary:
        archive = Path(temporary) / "tool.tar.gz"
        with urllib.request.urlopen(pin["url"], timeout=120) as response, archive.open("wb") as output:
            if not response.geturl().startswith("https://github.com/") and not response.geturl().startswith("https://release-assets.githubusercontent.com/"):
                raise ValueError("unexpected tool release redirect")
            shutil.copyfileobj(response, output)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != pin["sha256"]:
            raise ValueError(f"{name}: checksum mismatch")
        with tarfile.open(archive) as tar:
            member = tar.getmember(name)
            if not member.isfile() or member.size > 128 * 1024 * 1024:
                raise ValueError("unexpected tool binary member")
            source = tar.extractfile(member)
            if source is None:
                raise ValueError("missing binary")
            destination.mkdir(parents=True, exist_ok=True)
            target = destination / name
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
            target.chmod(0o755)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=("gitleaks", "actionlint"))
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(install(args.name, args.destination))
