#!/usr/bin/env python3
"""Read CS2's `cl_showfps` counter from the game window, without a debugger.

Why this exists: CS2 on this stack has no frametime export, and sampling the
window with `screencapture` at a short interval destroys the number being
measured (72 fps -> 3 fps, docs/07-benchmark-protocol.md). So this takes a few
widely spaced single readings and reports the median, and it labels the result
as screenshot-sampled rather than pretending to be a protocol run.

The counter is drawn in pure red, which is what makes it readable: isolate the
red pixels, crop to their bounding box, upscale, then OCR with macOS Vision.

Usage:  python3 scripts/fps_probe.py [samples] [interval_seconds]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time

import numpy as np
import Quartz
import Vision
from Foundation import NSURL
from PIL import Image

WINDOW_TITLE = "Counter-Strike 2"


def window_id():
    for wd in Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionAll | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID):
        if str(wd.get("kCGWindowName", "")) == WINDOW_TITLE:
            return int(wd.get("kCGWindowNumber"))
    return None


def capture(wid, path="/tmp/cs2kit_fps.png"):
    subprocess.run(["screencapture", "-l", str(wid), "-o", "-x", path],
                   capture_output=True, timeout=60)
    return path


def ocr(path):
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(
        NSURL.fileURLWithPath_(path), None)
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(0)
    request.setUsesLanguageCorrection_(False)
    handler.performRequests_error_([request], None)
    return [str(o.topCandidates_(1)[0].string())
            for o in (request.results() or []) if o.topCandidates_(1)]


def read_fps(png):
    im = Image.open(png).convert("RGB")
    arr = np.asarray(im.crop((0, 200, 700, 520)), dtype=np.int16)
    mask = (arr[:, :, 0] > 140) & (arr[:, :, 1] < 90) & (arr[:, :, 2] < 90)
    if mask.sum() < 30:
        return None
    ys, xs = np.nonzero(mask)
    box = (max(0, xs.min() - 6), max(0, ys.min() - 6),
           min(arr.shape[1], xs.max() + 6), min(arr.shape[0], ys.max() + 6))
    sub = np.where(mask, 0, 255).astype("uint8")[box[1]:box[3], box[0]:box[2]]
    img = Image.fromarray(sub).resize(((box[2] - box[0]) * 6, (box[3] - box[1]) * 6), Image.LANCZOS)
    img.save("/tmp/cs2kit_fps_crop.png")
    for text in ocr("/tmp/cs2kit_fps_crop.png"):
        m = re.search(r"(\d{1,3})\s*[fl]ps", text, re.I) or re.match(r"\s*(\d{1,3})\b", text)
        if m and 1 <= int(m.group(1)) <= 999:
            return int(m.group(1))
    return None


def main():
    samples = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    wid = window_id()
    if wid is None:
        print(json.dumps({"error": "no Counter-Strike 2 window"}))
        return 3
    readings = []
    for i in range(samples):
        if i:
            time.sleep(interval)
        value = read_fps(capture(wid))
        if value:
            readings.append(value)
    readings.sort()
    print(json.dumps({
        "method": "screenshot-sampled cl_showfps, median of instantaneous readings",
        "caveat": "each capture briefly perturbs the game; see docs/07-benchmark-protocol.md",
        "samples": readings,
        "median": readings[len(readings) // 2] if readings else None,
        "min": readings[0] if readings else None,
        "max": readings[-1] if readings else None,
    }, indent=2))
    return 0 if readings else 1


if __name__ == "__main__":
    raise SystemExit(main())
