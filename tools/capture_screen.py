#!/usr/bin/env python3
"""
Screen Capture Tool - Cross-platform (Windows/Linux)

Modes:
  list    - Enumerate visible top-level windows (Linux/X11) as JSON
  active  - Capture the currently focused window
  window  - Capture a specific X11 window by id (--window-id 0x...)
  full    - Capture full screen (optionally --monitor N)
  region  - Capture a rectangle (--left --top --width --height)

Saves to {project}/experiments/capture/YYYYMMDD_HHMMSS_<label>.png
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime


SAVE_SUBDIR = os.path.join("experiments", "capture")


def get_save_path(project_dir, label):
    """Create capture directory and return timestamped file path."""
    out_dir = os.path.join(project_dir, SAVE_SUBDIR)
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", label).strip("_") or "capture"
    safe = safe[:60]
    return os.path.join(out_dir, f"{ts}_{safe}.png")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


# ---------------------------------------------------------------------------
# X11 window listing / geometry via xwininfo
# ---------------------------------------------------------------------------

_TREE_LINE_RE = re.compile(
    r'^\s*(0x[0-9a-fA-F]+)\s+"([^"]*)"[^\n]*?\s+'
    r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+)\s+\+(-?\d+)\+(-?\d+)'
)


def list_windows_x11():
    """Return visible top-level windows.

    Each item: {id, title, x, y, w, h}
    """
    r = _run(["xwininfo", "-root", "-tree"])
    if r.returncode != 0:
        raise RuntimeError(f"xwininfo -root -tree failed: {r.stderr.strip()}")

    seen = set()
    windows = []
    for line in r.stdout.splitlines():
        m = _TREE_LINE_RE.match(line)
        if not m:
            continue
        wid, title, w, h, _rx, _ry, ax, ay = m.groups()
        w, h = int(w), int(h)
        ax, ay = int(ax), int(ay)
        if w < 50 or h < 50:
            continue  # skip tiny (docks, popups, tooltips)
        if not title.strip():
            continue  # skip untitled helpers
        if wid in seen:
            continue
        seen.add(wid)
        windows.append({
            "id": wid, "title": title,
            "x": ax, "y": ay, "w": w, "h": h,
        })
    return windows


def get_window_geometry_x11(wid):
    r = _run(["xwininfo", "-id", wid])
    if r.returncode != 0:
        raise RuntimeError(f"xwininfo -id {wid} failed: {r.stderr.strip()}")
    x = y = w = h = None
    title = ""
    for line in r.stdout.splitlines():
        s = line.strip()
        if s.startswith("xwininfo: Window id:"):
            m = re.search(r'"([^"]*)"', s)
            if m:
                title = m.group(1)
        elif s.startswith("Absolute upper-left X:"):
            x = int(s.split(":")[-1])
        elif s.startswith("Absolute upper-left Y:"):
            y = int(s.split(":")[-1])
        elif s.startswith("Width:"):
            w = int(s.split(":")[-1])
        elif s.startswith("Height:"):
            h = int(s.split(":")[-1])
    if None in (x, y, w, h):
        raise RuntimeError(f"incomplete geometry for {wid}")
    return {"id": wid, "title": title, "x": x, "y": y, "w": w, "h": h}


def get_active_window_id_x11():
    """Resolve the focused X11 window id. Prefer xdotool, fallback to xprop."""
    if shutil.which("xdotool"):
        r = _run(["xdotool", "getactivewindow"])
        if r.returncode == 0 and r.stdout.strip():
            try:
                wid_dec = int(r.stdout.strip())
                return f"0x{wid_dec:x}"
            except ValueError:
                pass
    r = _run(["xprop", "-root", "_NET_ACTIVE_WINDOW"])
    if r.returncode == 0:
        m = re.search(r"0x[0-9a-fA-F]+", r.stdout)
        if m:
            return m.group(0)
    raise RuntimeError(
        "cannot determine active window "
        "(install xdotool or ensure the WM advertises _NET_ACTIVE_WINDOW)"
    )


# ---------------------------------------------------------------------------
# Capture primitives — prefer PIL, fall back to mss
# ---------------------------------------------------------------------------

def _grab_bbox(left, top, width, height, out_path):
    """Capture absolute-coordinate rectangle to PNG."""
    try:
        from PIL import ImageGrab
        im = ImageGrab.grab(bbox=(left, top, left + width, top + height))
        im.save(out_path, "PNG")
        return out_path
    except Exception:
        pass
    import mss
    import mss.tools
    with mss.mss() as sct:
        shot = sct.grab({"left": left, "top": top, "width": width, "height": height})
        mss.tools.to_png(shot.rgb, shot.size, output=out_path)
    return out_path


def capture_full_screen(out_path, monitor_index=0):
    try:
        import mss
        import mss.tools
        with mss.mss() as sct:
            idx = monitor_index + 1
            monitor = sct.monitors[idx] if idx < len(sct.monitors) else sct.monitors[1]
            shot = sct.grab(monitor)
            mss.tools.to_png(shot.rgb, shot.size, output=out_path)
        return out_path
    except Exception:
        from PIL import ImageGrab
        im = ImageGrab.grab()
        im.save(out_path, "PNG")
        return out_path


def capture_region(out_path, left, top, width, height):
    return _grab_bbox(left, top, width, height, out_path)


def capture_active_window(out_path):
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return _grab_bbox(
            rect.left, rect.top,
            rect.right - rect.left, rect.bottom - rect.top,
            out_path,
        )
    wid = get_active_window_id_x11()
    g = get_window_geometry_x11(wid)
    return _grab_bbox(g["x"], g["y"], g["w"], g["h"], out_path)


def capture_window_by_id(out_path, wid):
    g = get_window_geometry_x11(wid)
    return _grab_bbox(g["x"], g["y"], g["w"], g["h"], out_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Screen Capture Tool")
    p.add_argument("--project", help="Project root directory (required for capture modes)")
    p.add_argument(
        "--mode",
        choices=["full", "active", "region", "window", "list"],
        default="active",
        help="Capture mode",
    )
    p.add_argument("--monitor", type=int, default=0, help="Monitor index for --mode full")
    p.add_argument("--left", type=int, default=0)
    p.add_argument("--top", type=int, default=0)
    p.add_argument("--width", type=int, default=800)
    p.add_argument("--height", type=int, default=600)
    p.add_argument("--window-id", dest="window_id",
                   help="X11 window id (hex, e.g. 0x2800008) for --mode window")
    p.add_argument("--label", default="capture",
                   help="Filename label suffix (e.g. firefox, vscode)")

    args = p.parse_args()

    if args.mode == "list":
        windows = list_windows_x11()
        print(json.dumps(windows, ensure_ascii=False, indent=2))
        return

    if not args.project:
        print("--project is required for capture modes", file=sys.stderr)
        sys.exit(2)

    save_path = get_save_path(args.project, args.label)

    if args.mode == "full":
        capture_full_screen(save_path, args.monitor)
    elif args.mode == "active":
        capture_active_window(save_path)
    elif args.mode == "region":
        capture_region(save_path, args.left, args.top, args.width, args.height)
    elif args.mode == "window":
        if not args.window_id:
            print("--window-id is required for --mode window", file=sys.stderr)
            sys.exit(2)
        capture_window_by_id(save_path, args.window_id)

    print(save_path)


if __name__ == "__main__":
    main()
