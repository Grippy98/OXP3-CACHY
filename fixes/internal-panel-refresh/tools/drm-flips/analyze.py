#!/usr/bin/env python3
"""Summarize delivered DRM-event cadence by file and CRTC from ftrace text."""
import argparse
import collections
import json
import math
import re
import statistics
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("trace", type=Path)
args = parser.parse_args()
groups = collections.defaultdict(list)
pattern = re.compile(r"(\d+\.\d+): drm_vblank_event_delivered: file=([^,]+), crtc=(\d+), seq=(\d+)")
for line in args.trace.read_text().splitlines():
    match = pattern.search(line)
    if match:
        timestamp, file_id, crtc, sequence = match.groups()
        groups[(file_id, int(crtc))].append((float(timestamp), int(sequence)))
results = []
for (file_id, crtc), events in groups.items():
    gaps = [(new[0] - old[0]) * 1000 for old, new in zip(events, events[1:])]
    ordered = sorted(gaps)
    results.append({
        "file_token": file_id, "crtc_index": crtc, "events": len(events),
        "first_sequence": events[0][1], "last_sequence": events[-1][1],
        "delivered_rate_hz": (len(events) - 1) / (events[-1][0] - events[0][0]) if gaps else None,
        "median_interval_ms": statistics.median(gaps) if gaps else None,
        "p95_interval_ms": ordered[math.ceil(.95 * len(ordered)) - 1] if ordered else None,
        "nonpositive_intervals": sum(gap <= 0 for gap in gaps),
    })
print(json.dumps({"groups": results, "percentile": "nearest rank", "scope": "Ftrace dispatch timestamps of delivered DRM events; no game identity or first-visible timestamp."}, indent=2))
