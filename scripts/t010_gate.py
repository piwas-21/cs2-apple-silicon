#!/usr/bin/env python3
"""T-010 gate: two passes per map, bots joined, FPS sampled by on-screen OCR."""
import json, os, re, subprocess, sys, time
import Quartz, Vision
from Foundation import NSURL
from PIL import Image

HOME = os.path.expanduser("~")
SK = f"{HOME}/CS2/wine-sk/wswine.bundle"
GAME = (f"{HOME}/Library/Application Support/Steam/steamapps/common/"
        "Counter-Strike Global Offensive/game/bin/win64")
ENV = dict(os.environ)
ENV.update({"WINEPREFIX": f"{HOME}/CS2/prefix-sk", "PATH": f"{SK}/bin:" + os.environ["PATH"],
            "DYLD_FALLBACK_LIBRARY_PATH": f"{SK}/lib", "WINEDEBUG": "-all", "WINEMSYNC": "1"})
LOG = open(f"{HOME}/CS2/t010-gate.jsonl", "a", buffering=1)
MAPS = ["de_dust2", "de_mirage", "de_ancient"]
PASSES = 2
MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0


def rec(**kw):
    kw["t"] = time.strftime("%H:%M:%S")
    LOG.write(json.dumps(kw) + "\n")


def sh(cmd, timeout=180):
    return subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, env=ENV, timeout=timeout)


def window():
    for wd in Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionAll | Quartz.kCGWindowListExcludeDesktopElements, Quartz.kCGNullWindowID):
        if str(wd.get("kCGWindowName", "")) == "Counter-Strike 2":
            b = wd.get("kCGWindowBounds", {})
            return {"id": int(wd.get("kCGWindowNumber")), "x": int(b.get("X", 0)), "y": int(b.get("Y", 0)),
                    "w": int(b.get("Width", 0)), "h": int(b.get("Height", 0))}
    return None


def shot(win, path="/tmp/gate_s.png"):
    subprocess.run(["screencapture", "-l", str(win["id"]), "-o", "-x", path], capture_output=True, timeout=60)
    return path if os.path.exists(path) else None


def ocr(path):
    url = NSURL.fileURLWithPath_(path)
    h = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, None)
    r = Vision.VNRecognizeTextRequest.alloc().init()
    r.setRecognitionLevel_(0)
    h.performRequests_error_([r], None)
    return [str(o.topCandidates_(1)[0].string()) for o in (r.results() or []) if o.topCandidates_(1)]


def fps_of(path):
    im = Image.open(path).crop((0, 320, 760, 420))
    im = im.resize((im.width * 4, im.height * 4))
    im.save("/tmp/gate_fps.png")
    for s in ocr("/tmp/gate_fps.png"):
        m = re.search(r"(\d{2,3})\s*fps", s, re.I)
        if m:
            v = int(m.group(1))
            if 5 <= v <= 999:
                return v
    return None


def thumb(path):
    im = Image.open(path).convert("RGB").resize((160, 100))
    px = list(im.getdata())
    return {"mean": round(sum(sum(q) for q in px) / (3 * len(px)), 1), "px": px[::200]}


def key(code):
    src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    d = Quartz.CGEventCreateKeyboardEvent(src, code, True)
    u = Quartz.CGEventCreateKeyboardEvent(src, code, False)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, d); time.sleep(0.06)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, u); time.sleep(0.3)


def click(x, y):
    p = Quartz.CGPointMake(float(x), float(y))
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, p, 0))
    time.sleep(0.2)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, p, 0))
    time.sleep(0.08)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, p, 0))
    time.sleep(0.3)


def focus():
    subprocess.run(["osascript", "-e",
                    'tell application "System Events" to tell process "wine" to set frontmost to true'],
                   capture_output=True, timeout=30)


for mp in MAPS:
    for pas in range(1, PASSES + 1):
        sh("pkill -f cs2.exe; sleep 4")
        args = ("-novid -nojoy -console +exec cs2kit +exec cs2kit_gate "
                f"+game_type 0 +game_mode 0 +sv_lan 1 +map {mp}")
        subprocess.Popen(["bash", "-lc", f'cd "{GAME}" && exec wine cs2.exe {args}'],
                         stdout=open(f"{HOME}/CS2/cs2-{mp}-p{pas}.log", "w"), stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, env=ENV, start_new_session=True)
        rec(event="launch", map=mp, **{"pass": pas})
        win = None
        t0 = time.time()
        for _ in range(24):
            time.sleep(15)
            win = window()
            if win:
                s = shot(win)
                if s and thumb(s)["mean"] > 20:
                    break
        if not win:
            rec(event="FAIL_no_window", map=mp, **{"pass": pas})
            continue
        rec(event="loaded", map=mp, load_s=round(time.time() - t0), **{"pass": pas})

        focus(); time.sleep(1)
        click(win["x"] + win["w"] * 0.5, win["y"] + win["h"] * 0.5)   # focus the game surface
        time.sleep(1)
        key(109)          # F10 -> jointeam 2
        time.sleep(8)
        key(103)          # F11 -> bot_quota 10; mp_restartgame 1
        time.sleep(15)

        # Sampling perturbs the thing being measured: capturing this window every
        # 20 s dropped the game from 72 fps to 3 fps (measured 2026-08-24). So the
        # cheap signals run often and the screenshot runs rarely.
        prev, frozen, crashed, fps = None, 0, False, []
        end = time.time() + MINUTES * 60
        last_shot = 0.0
        while time.time() < end:
            time.sleep(20)
            if time.time() - last_shot < 240:
                if sh("pgrep -f cs2.exe | wc -l").stdout.strip() == "0":
                    crashed = True
                    rec(event="CRASH", map=mp, **{"pass": pas})
                    break
                rec(event="alive", map=mp, rss_mb=None, **{"pass": pas})
                continue
            last_shot = time.time()
            if sh("pgrep -f cs2.exe | wc -l").stdout.strip() == "0" or window() is None:
                crashed = True
                rec(event="CRASH", map=mp, **{"pass": pas})
                break
            s = shot(window())
            th = thumb(s) if s else None
            f = fps_of(s) if s else None
            if f:
                fps.append(f)
            same = bool(prev and th and prev["px"] == th["px"])
            frozen += int(same)
            rec(event="sample", map=mp, fps=f, mean=(th or {}).get("mean"), frozen=same, **{"pass": pas})
            prev = th
        ordered = sorted(fps)
        rec(event="pass_done", map=mp, crashed=crashed, frozen_samples=frozen, fps_samples=len(fps),
            fps_median=(ordered[len(ordered)//2] if ordered else None),
            fps_min=(ordered[0] if ordered else None), fps_max=(ordered[-1] if ordered else None),
            **{"pass": pas})

rec(event="gate_done", maps=MAPS, passes=PASSES, minutes=MINUTES)
