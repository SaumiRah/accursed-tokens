"""
Unit tests for technique detection.

Run: pytest tests/test_techniques.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from detect import NoteEvent
from fretboard import Placement, ChordGroup, place
from techniques import (
    annotate,
    _annotate_single,
    _annotate_transitions,
    BEND_MIN_SEMITONES,
    HAMMER_PULL_WINDOW,
    SLIDE_WINDOW,
    SLIDE_MIN_FRET_DIST,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _placement(string: int, fret: int, onset: float = 0.0, offset: float = 0.5,
               pitch_bends: list | None = None) -> Placement:
    return Placement(
        onset=onset, offset=offset,
        midi_pitch=40 + fret,
        string=string, fret=fret,
        confidence=0.9,
        pitch_bends=pitch_bends or [],
    )


def _group(*placements: Placement) -> ChordGroup:
    return ChordGroup(list(placements))


# ── Bend detection ────────────────────────────────────────────────────────────

class TestBendDetection:
    def test_no_bends_no_annotation(self):
        p = _placement(1, 7)
        _annotate_single(p)
        assert p.technique_self == ""

    def test_bend_detected_above_threshold(self):
        p = _placement(1, 7, pitch_bends=[0.0, 0.2, 0.5, 0.8, 1.0])
        _annotate_single(p)
        assert p.technique_self == "b"

    def test_bend_below_threshold_ignored(self):
        p = _placement(1, 7, pitch_bends=[0.0, 0.1, 0.2, 0.1])
        _annotate_single(p)
        assert p.technique_self == ""

    def test_bend_target_fret_computed(self):
        # Bends 2 semitones up from fret 7 → target fret 9
        p = _placement(1, 7, pitch_bends=[0.0, 1.0, 1.8, 2.0, 2.0])
        _annotate_single(p)
        assert p.technique_self == "b"
        assert p.bend_target_fret == 9

    def test_bend_target_fret_half_step(self):
        # Bends 1 semitone up from fret 5 → target fret 6
        p = _placement(1, 5, pitch_bends=[0.0, 0.5, 0.9, 1.0])
        _annotate_single(p)
        assert p.technique_self == "b"
        assert p.bend_target_fret == 6

    def test_bend_no_target_when_zero_semitones(self):
        # Just above threshold but rounds to 0 semitones
        p = _placement(1, 7, pitch_bends=[0.0, 0.41, 0.42])
        _annotate_single(p)
        # technique_self may be "b" but bend_target_fret should remain None
        if p.technique_self == "b":
            # bend_semis = round(0.42) = 0, so no target
            assert p.bend_target_fret is None


# ── Vibrato detection ─────────────────────────────────────────────────────────

class TestVibratoDetection:
    def test_vibrato_detected_with_oscillations(self):
        # Oscillates: +0.3, -0.3, +0.3, -0.3 → many zero crossings
        bends = [0.3, 0.1, -0.1, -0.3, -0.1, 0.1, 0.3, 0.1, -0.1, -0.3]
        p = _placement(1, 7, pitch_bends=bends)
        _annotate_single(p)
        assert p.technique_self == "~"

    def test_vibrato_not_detected_too_few_crossings(self):
        # Only one cycle (one up, one down) — not enough for vibrato
        p = _placement(1, 7, pitch_bends=[0.0, 0.3, 0.3, -0.1])
        _annotate_single(p)
        # With only 1 crossing: not vibrato
        assert p.technique_self != "~"

    def test_sustained_bend_not_vibrato(self):
        # Monotonically increasing → bend, not vibrato
        p = _placement(1, 7, pitch_bends=[0.0, 0.3, 0.6, 0.9, 1.2, 1.5, 1.8])
        _annotate_single(p)
        assert p.technique_self == "b"

    def test_empty_bends_no_annotation(self):
        p = _placement(1, 7, pitch_bends=[])
        _annotate_single(p)
        assert p.technique_self == ""
        assert p.technique_incoming == ""


# ── Hammer-on / pull-off detection ───────────────────────────────────────────

class TestHammerOnPullOff:
    def test_hammer_on_ascending(self):
        g1 = _group(_placement(1, 5, onset=0.0, offset=0.1))
        g2 = _group(_placement(1, 7, onset=0.08, offset=0.5))
        _annotate_transitions([g1, g2])
        assert g2.placements[0].technique_incoming == "h"

    def test_pull_off_descending(self):
        g1 = _group(_placement(1, 7, onset=0.0, offset=0.1))
        g2 = _group(_placement(1, 5, onset=0.08, offset=0.5))
        _annotate_transitions([g1, g2])
        assert g2.placements[0].technique_incoming == "p"

    def test_pull_off_to_open_string(self):
        g1 = _group(_placement(1, 3, onset=0.0, offset=0.1))
        g2 = _group(_placement(1, 0, onset=0.08, offset=0.5))
        _annotate_transitions([g1, g2])
        assert g2.placements[0].technique_incoming == "p"

    def test_hammer_on_not_to_open_string(self):
        # Ascending but target is open string → not a hammer-on
        g1 = _group(_placement(2, 3, onset=0.0, offset=0.4))
        g2 = _group(_placement(2, 0, onset=0.05, offset=0.5))  # This is descending anyway
        _annotate_transitions([g1, g2])
        # fret_diff is -3, so it's a pull-off, not hammer-on
        assert g2.placements[0].technique_incoming == "p"

    def test_no_technique_when_gap_too_large(self):
        g1 = _group(_placement(1, 5, onset=0.0, offset=0.1))
        g2 = _group(_placement(1, 7, onset=1.0, offset=1.5))  # 1s gap → too slow
        _annotate_transitions([g1, g2])
        assert g2.placements[0].technique_incoming == ""

    def test_no_technique_on_different_strings(self):
        g1 = _group(_placement(1, 5, onset=0.0, offset=0.1))
        g2 = _group(_placement(2, 7, onset=0.05, offset=0.5))  # different string
        _annotate_transitions([g1, g2])
        assert g2.placements[0].technique_incoming == ""

    def test_no_technique_same_fret(self):
        g1 = _group(_placement(1, 7, onset=0.0, offset=0.1))
        g2 = _group(_placement(1, 7, onset=0.05, offset=0.5))
        _annotate_transitions([g1, g2])
        assert g2.placements[0].technique_incoming == ""


# ── Slide detection ───────────────────────────────────────────────────────────

class TestSlide:
    def test_slide_up(self):
        g1 = _group(_placement(2, 3, onset=0.0, offset=0.1))
        g2 = _group(_placement(2, 7, onset=0.20, offset=0.6))
        _annotate_transitions([g1, g2])
        assert g2.placements[0].technique_incoming == "/"

    def test_slide_down(self):
        g1 = _group(_placement(2, 9, onset=0.0, offset=0.1))
        g2 = _group(_placement(2, 4, onset=0.20, offset=0.6))
        _annotate_transitions([g1, g2])
        assert g2.placements[0].technique_incoming == "\\"

    def test_slide_requires_min_fret_distance(self):
        g1 = _group(_placement(2, 5, onset=0.0, offset=0.1))
        g2 = _group(_placement(2, 7, onset=0.20, offset=0.6))
        _annotate_transitions([g1, g2])
        # 2 frets apart with 0.20s onset gap: abs_diff=2 < SLIDE_MIN_FRET_DIST=4, not a slide.
        # But gap=0.20 >= HAMMER_PULL_WINDOW=0.15, not h/p either → no annotation.
        assert g2.placements[0].technique_incoming == ""

    def test_no_slide_when_gap_too_large(self):
        g1 = _group(_placement(2, 3, onset=0.0, offset=0.1))
        g2 = _group(_placement(2, 9, onset=0.5, offset=1.0))  # 0.5s → too slow
        _annotate_transitions([g1, g2])
        assert g2.placements[0].technique_incoming == ""


# ── annotate() full pipeline ──────────────────────────────────────────────────

class TestAnnotateFull:
    def test_annotate_does_not_raise_on_empty(self):
        annotate([])  # should not raise

    def test_annotate_does_not_raise_on_no_bends(self):
        g = _group(_placement(1, 5))
        annotate([g])
        assert g.placements[0].technique_self == ""
        assert g.placements[0].technique_incoming == ""

    def test_annotate_combines_bend_and_transition(self):
        # A hammer-on note that also has a bend
        g1 = _group(_placement(1, 5, onset=0.0, offset=0.1))
        bend_bends = [0.0, 0.5, 1.0, 1.5, 2.0]
        g2 = _group(_placement(1, 7, onset=0.08, offset=0.6, pitch_bends=bend_bends))
        annotate([g1, g2])
        p2 = g2.placements[0]
        assert p2.technique_incoming == "h"  # hammer-on from g1
        assert p2.technique_self == "b"      # bend on this note
        assert p2.bend_target_fret == 9      # bent 2 semitones up

    def test_annotate_from_placed_notes(self):
        """Smoke test: annotate a full pipeline output."""
        events = [
            NoteEvent(onset=0.0, offset=0.4, midi_pitch=64, confidence=0.9),
            NoteEvent(onset=0.5, offset=0.9, midi_pitch=66, confidence=0.9),
            NoteEvent(onset=1.0, offset=1.4, midi_pitch=69, confidence=0.8),
        ]
        from fretboard import place
        chord_groups = place(events)
        annotate(chord_groups)  # should not raise
        # All placements should still have valid frets
        for group in chord_groups:
            for p in group.placements:
                assert 0 <= p.fret <= 22
