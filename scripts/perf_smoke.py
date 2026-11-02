"""Offline CLI budgets on synthetic data. These results are not game FPS."""
from __future__ import annotations

import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cs2kit import engine, recipe


def measure(call, budget):
    call()  # Discard a warm-up; retain every measured sample.
    samples = []
    for _ in range(5):
        start = time.perf_counter()
        call()
        samples.append(time.perf_counter() - start)
    median = statistics.median(samples)
    return {"samples_seconds": samples, "median_seconds": median,
            "budget_seconds": budget, "passed": median <= budget}


def main():
    with tempfile.TemporaryDirectory(prefix="cs2kit-perf-") as temporary:
        home = Path(temporary)
        env = dict(os.environ, HOME=str(home), CS2KIT_HOME=str(home / "state"),
                   WINEPREFIX=str(home / "prefix"), CS2KIT_REPO=str(ROOT), PYTHONPATH=str(ROOT))
        env.pop("PYTHONSTARTUP", None)
        blob = home / "hash.bin"
        blob.write_bytes(b"x" * (16 * 1024 * 1024))
        profile = (ROOT / "profiles/balanced-1080p.yaml").read_text()

        def help_command():
            subprocess.run([sys.executable, "-m", "cs2kit", "--help"], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True, timeout=10)

        def parse_profiles():
            for _ in range(100):
                recipe.loads(profile).require_valid()

        results = {"cli_help": measure(help_command, 2.0),
                   "parse_100_profiles": measure(parse_profiles, 0.5),
                   "sha256_16_mib": measure(lambda: engine.sha256_of(blob), 0.5)}
    report = {"python": platform.python_version(), "platform": platform.system(),
              "method": "one discarded warm-up, five samples, median; synthetic offline workloads",
              "results": results}
    (ROOT / "performance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if all(result["passed"] for result in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
