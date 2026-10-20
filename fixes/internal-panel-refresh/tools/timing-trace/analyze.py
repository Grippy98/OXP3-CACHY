#!/usr/bin/env python3
"""Summarize bounded Gamescope diagnostic records; IDs come from submits."""
import argparse
import collections
import json
import re
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("trace", type=Path)
p.add_argument("--first", type=int, default=0)
p.add_argument("--last", type=int, default=2**64)
p.add_argument("--app", type=int, default=1710820)
a = p.parse_args()
events = []
for line in a.trace.read_text().splitlines():
    if "timing-trace event=" not in line:
        continue
    fields = dict(re.findall(r"(\w+)=([^\s]+)", line))
    seq = int(fields.get("seq", "0"))
    if a.first <= seq <= a.last:
        for k, v in fields.items():
            if re.fullmatch(r"-?\d+", v):
                fields[k] = int(v)
        events.append(fields)
timers = {e["seq"]: e for e in events if e["event"] == "timer"}
flips = [e for e in events if e["event"] == "pageflip" and e["seq"] in timers]
game_flips = []
first_timer = next(iter(timers.values()), {})
previous = (first_timer.get("base_app"), first_timer.get("base_commit"))
for e in flips:
    identity = (e.get("base_app"), e.get("base_commit"))
    if identity != previous and identity[0] == a.app:
        game_flips.append(e)
    previous = identity
def intervals(items, key):
    return collections.Counter(round((b[key] - c[key]) / 1e6, 2)
                               for c, b in zip(items, items[1:]))
timer_list = list(timers.values())
fixed_only = all(not e["vrr"] for e in timer_list)
late = [e for e in game_flips
        if e["flip_ns"] - timers[e["seq"]]["target_ns"] > 1_000_000]
summary = {
    "file": str(a.trace), "first_seq": min(timers, default=None),
    "last_seq": max(timers, default=None), "timers": len(timers),
    "caps": dict(collections.Counter(e["cap"] for e in timer_list)),
    "refresh_mhz": dict(collections.Counter(e["refresh_mhz"] for e in timer_list)),
    "vrr": dict(collections.Counter(e["vrr"] for e in timer_list)),
    "timer_target_intervals_ms": dict(intervals(timer_list, "target_ns")),
    "timer_dispatch_intervals_ms": dict(intervals(timer_list, "processed_ns")),
    "pageflips": len(flips), "new_game_flips": len(game_flips),
    "late_new_game_flips": len(late) if fixed_only else None,
    "game_flip_intervals_ms": dict(intervals(game_flips, "flip_ns")),
    "target_advance_periods": dict(collections.Counter(
        e.get("target_advance_periods", 0) for e in timer_list)),
    "note": "Bounded logging may omit records; trace overhead applies. New-game transitions use per-submit identity, not Mango telemetry. Fixed-refresh target lateness is not applied to VRR.",
}
if len(game_flips) > 1:
    summary["physical_game_transition_rate_hz"] = (len(game_flips)-1)*1e9/(game_flips[-1]["flip_ns"]-game_flips[0]["flip_ns"])
print(json.dumps(summary, indent=2))
