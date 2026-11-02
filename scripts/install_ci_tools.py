"""Install one pinned CI binary after checksum verification; never extract paths."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tarfile
import tempfile
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path


REPOSITORIES = {"gitleaks": "gitleaks/gitleaks", "actionlint": "rhysd/actionlint"}


def validate_url(url: str) -> None:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in
            {"github.com", "release-assets.githubusercontent.com"} or parsed.port not in (None, 443)
            or parsed.username or parsed.password):
        raise ValueError("unexpected tool release URL")


class ReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def install(name: str) -> Path:
    if name not in REPOSITORIES:
        raise ValueError("unknown CI tool")
    pins = json.loads((Path(__file__).resolve().parent.parent / ".github/ci-tools.json").read_text())
    pin = pins[name]
    validate_url(pin["url"])
    if not pin["url"].startswith(f"https://github.com/{REPOSITORIES[name]}/releases/download/"):
        raise ValueError("tool must come from its official release repository")
    if not re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]):
        raise ValueError("invalid tool checksum")
    with tempfile.TemporaryDirectory(prefix="cs2kit-ci-tool-") as temporary:
        archive = Path(temporary) / "tool.tar.gz"
        opener = urllib.request.build_opener(ReleaseRedirect())
        with opener.open(pin["url"], timeout=120) as response, archive.open("wb") as output:
            validate_url(response.geturl())
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
            # Do not accept a caller-supplied output path or reuse a directory.
            # The runner cleans its temporary storage after the job finishes.
            destination = Path(tempfile.mkdtemp(prefix="cs2kit-ci-bin-", dir=os.environ.get("RUNNER_TEMP")))
            target = destination / name
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
            target.chmod(0o755)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=("gitleaks", "actionlint"))
    args = parser.parse_args()
    print(install(args.name))
