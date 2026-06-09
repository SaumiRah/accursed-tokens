"""
Guitar technique detection.

Annotates ChordGroup placements with guitar playing techniques by analysing:
  - pitch_bends data from BasicPitch → bends, vibrato
  - timing + pitch relationships between consecutive notes on the same string → h/p/slide

Call annotate(chord_groups) after fretboard.place(). It mutates placements in place.

Technique codes stored on Placement:
  technique_incoming  "h" hammer-on, "p" pull-off, "/" slide-up, "\\" slide-down
  technique_self      "b" bend, "~" vibrato
  bend_target_fret    int  (fret equivalent of the bent-to pitch, for "b" only)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from fretboard import ChordGroup, Placement

# ── Thresholds ────────────────────────────────────────────────────────────────

BEND_MIN_SEMITONES = 0.40      # minimum peak pitch deviation to call it a bend
VIBRATO_MIN_AMP = 0.15         # minimum peak-to-peak amplitude (semitones) for vibrato
VIBRATO_MIN_CROSSINGS = 3      # minimum zero-crossings to distinguish vibrato from bend

HAMMER_PULL_WINDOW = 0.15      # max onset-to-onset gap (seconds) for h/p
SLIDE_WINDOW = 0.30            # max onset-to-onset gap (seconds) for slide
SLIDE_MIN_FRET_DIST = 4        # minimum fret distance to call it a slide (not h/p)


# ── Per-note annotation ───────────────────────────────────────────────────────

def _annotate_single(p: Placement) -> None:
    """Detect bend or vibrato from a placement's pitch_bends vector."""
    bends = p.pitch_bends
    if not bends:
        return

    max_dev = max(bends)
    min_dev = min(bends)

    # Zero crossings: sign changes (with a small dead-zone to filter noise)
    crossings = 0
    for i in range(1, len(bends)):
        if bends[i - 1] > 0.05 and bends[i] < -0.05:
            crossings += 1
        elif bends[i - 1] < -0.05 and bends[i] > 0.05:
            crossings += 1

    peak_to_peak = max_dev - min_dev

    if crossings >= VIBRATO_MIN_CROSSINGS and peak_to_peak >= 2 * VIBRATO_MIN_AMP:
        p.technique_self = "~"
    elif max_dev >= BEND_MIN_SEMITONES and crossings < VIBRATO_MIN_CROSSINGS:
        p.technique_self = "b"
        bend_semis = round(max_dev)
        if bend_semis > 0:
            p.bend_target_fret = p.fret + bend_semis


# ── Transition annotation ─────────────────────────────────────────────────────

def _annotate_transitions(chord_groups: Sequence[ChordGroup]) -> None:
    """Detect hammer-ons, pull-offs, and slides between consecutive notes on each string."""
    per_string: dict[int, list[Placement]] = defaultdict(list)
    for group in chord_groups:
        for p in group.placements:
            per_string[p.string].append(p)

    for string_placements in per_string.values():
        string_placements.sort(key=lambda p: p.onset)
        for i in range(1, len(string_placements)):
            prev = string_placements[i - 1]
            curr = string_placements[i]

            onset_gap = curr.onset - prev.onset
            fret_diff = curr.fret - prev.fret

            if onset_gap <= 0 or fret_diff == 0:
                continue

            abs_diff = abs(fret_diff)

            if onset_gap < HAMMER_PULL_WINDOW and abs_diff < SLIDE_MIN_FRET_DIST:
                # Hammer-on: ascending, target must be a fretted note
                if fret_diff > 0 and curr.fret > 0:
                    curr.technique_incoming = "h"
                # Pull-off: descending (can land on open string)
                elif fret_diff < 0:
                    curr.technique_incoming = "p"
            elif onset_gap < SLIDE_WINDOW and abs_diff >= SLIDE_MIN_FRET_DIST:
                curr.technique_incoming = "/" if fret_diff > 0 else "\\"


# ── Public API ────────────────────────────────────────────────────────────────

def annotate(chord_groups: Sequence[ChordGroup]) -> None:
    """
    Detect and annotate guitar techniques. Mutates placements in place.

    Must be called after fretboard.place() and before tab.render().

    Args:
        chord_groups: Output of fretboard.place() — list of ChordGroup with Placements.
    """
    for group in chord_groups:
        for p in group.placements:
            _annotate_single(p)
    _annotate_transitions(chord_groups)
