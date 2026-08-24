#!/usr/bin/env python3
"""Sample a running CS2 for N minutes: liveness, luminance, frozen frames, RSS."""
import json, os, subprocess, sys, time
import Quartz
from PIL import Image

HOME = os.path.expanduser("~")
MAP = sys.argv[1]; MINUTES = float(sys.argv[2])
LOG = open(f"{HOME}/CS2/t010-log.jsonl", "a", buffering=1)

def win():
    for wd in Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionAll | Quartz.kCGWindowListExcludeDesktopElements, Quartz.kCGNullWindowID):
        if str(wd.get("kCGWindowName", "")) == "Counter-Strike 2":
            return int(wd.get("kCGWindowNumber"))
    return None

def frame(wid):
    p = "/tmp/t010m.png"
    subprocess.run(["screencapture", "-l", str(wid), "-o", "-x", p], capture_output=True, timeout=60)
    if not os.path.exists(p): return None
    im = Image.open(p).convert("RGB").resize((160, 100)); px = list(im.getdata())
    return {"mean": round(sum(sum(q) for q in px)/(3*len(px)), 1),
            "nonblack": round(sum(1 for q in px if max(q) > 30)/len(px), 3), "px": px[::200]}

def rss():
    out = subprocess.run(["bash","-lc","ps -o rss= -p $(pgrep -f cs2.exe | head -1) 2>/dev/null"],
                         capture_output=True, text=True).stdout.strip()
    return int(out)//1024 if out.isdigit() else None

def rec(**kw):
    kw["t"] = time.strftime("%H:%M:%S"); kw["map"] = MAP
    LOG.write(json.dumps(kw) + "\n")

prev = None; frozen = 0; samples = 0; end = time.time() + MINUTES*60
rec(event="monitor_start", minutes=MINUTES)
while time.time() < end:
    time.sleep(30)
    alive = subprocess.run(["bash","-lc","pgrep -f cs2.exe | wc -l"], capture_output=True, text=True).stdout.strip()
    wid = win()
    if alive == "0" or wid is None:
        rec(event="CRASH", alive=alive); break
    f = frame(wid); samples += 1
    same = bool(prev and f and prev["px"] == f["px"])
    frozen += int(same)
    rec(event="sample", mean=(f or {}).get("mean"), nonblack=(f or {}).get("nonblack"),
        rss_mb=rss(), frozen=same)
    prev = f
rec(event="monitor_done", samples=samples, frozen_samples=frozen)
