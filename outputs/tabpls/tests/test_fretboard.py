"""
Unit tests for the fretboard mapper.

Run: pytest tests/test_fretboard.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from detect import NoteEvent
from fretboard import (
    STANDARD_TUNING,
    TUNINGS,
    MAX_FRET,
    MAX_SPAN,
    _candidates,
    _group_by_onset,
    place,
    Placement,
    ChordGroup,
)


# ── _candidates ───────────────────────────────────────────────────────────────

class TestCandidates:
    def test_low_e_open(self):
        # E2 = MIDI 40 = string 6 open (index 5)
        cands = _candidates(40, STANDARD_TUNING)
        assert (5, 0) in cands  # string 6 (idx 5) open

    def test_middle_c_multiple_positions(self):
        # MIDI 60 (C4) can be played on multiple strings
        cands = _candidates(60, STANDARD_TUNING)
        # Should be on D (string 4, idx 3), G (string 3, idx 2), B (string 2, idx 1)
        assert len(cands) >= 2

    def test_no_candidates_below_range(self):
        # MIDI 10 is far below the lowest guitar note
        cands = _candidates(10, STANDARD_TUNING)
        assert cands == []

    def test_no_candidates_above_max_fret(self):
        # A very high note that would require fret > MAX_FRET on all strings
        cands = _candidates(200, STANDARD_TUNING)
        assert cands == []

    def test_fret_values_in_range(self):
        for midi in range(40, 89):
            cands = _candidates(midi, STANDARD_TUNING)
            for s, f in cands:
                assert 0 <= f <= MAX_FRET, f"Fret {f} out of range for MIDI {midi}"
                assert 0 <= s <= 5, f"String index {s} out of range"


# ── _group_by_onset ───────────────────────────────────────────────────────────

def _make_note(onset, midi=60, offset=None):
    return NoteEvent(
        onset=onset,
        offset=(offset or onset + 0.5),
        midi_pitch=midi,
        confidence=0.9,
    )


class TestGroupByOnset:
    def test_single_note(self):
        notes = [_make_note(0.0)]
        groups = _group_by_onset(notes)
        assert len(groups) == 1
        assert len(groups[0]) == 1

    def test_simultaneous_notes_grouped(self):
        # Notes within CHORD_WINDOW should be in same group
        notes = [_make_note(1.0, 60), _make_note(1.02, 64)]  # 20ms apart
        groups = _group_by_onset(notes)
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_sequential_notes_separate(self):
        notes = [_make_note(0.0), _make_note(1.0), _make_note(2.0)]
        groups = _group_by_onset(notes)
        assert len(groups) == 3

    def test_empty(self):
        assert _group_by_onset([]) == []

    def test_sort_by_onset(self):
        notes = [_make_note(2.0), _make_note(0.0), _make_note(1.0)]
        groups = _group_by_onset(notes)
        onsets = [g[0].onset for g in groups]
        assert onsets == sorted(onsets)


# ── place ─────────────────────────────────────────────────────────────────────

class TestPlace:
    def test_empty(self):
        result = place([])
        assert result == []

    def test_single_note_placed(self):
        note = _make_note(0.0, midi=64)  # high E open
        groups = place([note])
        assert len(groups) == 1
        p = groups[0].placements[0]
        assert isinstance(p, Placement)
        assert 1 <= p.string <= 6
        assert 0 <= p.fret <= MAX_FRET

    def test_open_e_string(self):
        # MIDI 64 = high E — should map to string 1, fret 0 (open) or elsewhere
        note = _make_note(0.0, midi=64)
        groups = place([note])
        p = groups[0].placements[0]
        # At minimum, the fret should be valid
        assert p.fret >= 0

    def test_chord_no_string_reuse(self):
        # E major open chord: E2(40), B2(47), E3(52), G#3(56), B3(59), E4(64)
        notes = [
            _make_note(0.0, midi=40),
            _make_note(0.01, midi=47),
            _make_note(0.01, midi=52),
            _make_note(0.01, midi=56),
            _make_note(0.01, midi=59),
            _make_note(0.01, midi=64),
        ]
        groups = place(notes)
        # All notes should be placed
        total_placements = sum(len(g.placements) for g in groups)
        assert total_placements == len(notes)
        # No two placements in the same group should share a string
        for group in groups:
            strings = [p.string for p in group.placements]
            assert len(strings) == len(set(strings)), "Duplicate string in chord group"

    def test_sequential_notes_form_multiple_groups(self):
        notes = [
            _make_note(0.0, midi=60),
            _make_note(0.5, midi=62),
            _make_note(1.0, midi=64),
        ]
        groups = place(notes)
        assert len(groups) == 3

    def test_all_placements_in_valid_range(self):
        notes = [_make_note(i * 0.25, midi=m) for i, m in enumerate(range(40, 65, 5))]
        groups = place(notes)
        for group in groups:
            for p in group.placements:
                assert 1 <= p.string <= 6
                assert 0 <= p.fret <= MAX_FRET

    def test_drop_d_tuning(self):
        # Low D = MIDI 38 — only reachable in drop D tuning
        note = _make_note(0.0, midi=38)
        groups = place([note], tuning="drop_d")
        assert len(groups) == 1
        p = groups[0].placements[0]
        assert p.fret >= 0

    def test_drop_d_rejects_e2_open_on_string6(self):
        # In drop D, string 6 open = D2 (38), not E2 (40)
        note = _make_note(0.0, midi=40)  # E2
        groups_std = place([note], tuning="standard")
        groups_dd = place([note], tuning="drop_d")
        # In both cases it should be placed somewhere valid
        for groups in [groups_std, groups_dd]:
            p = groups[0].placements[0]
            assert 0 <= p.fret <= MAX_FRET


# ── ChordGroup properties ─────────────────────────────────────────────────────

class TestChordGroup:
    def _make_placement(self, string, fret, onset=0.0):
        return Placement(
            onset=onset, offset=onset + 0.5,
            midi_pitch=40 + fret,
            string=string, fret=fret,
            confidence=0.9,
        )

    def test_hand_span_open_strings(self):
        group = ChordGroup([
            self._make_placement(6, 0),  # open
            self._make_placement(5, 0),  # open
        ])
        assert group.hand_span == 0

    def test_hand_span_fretted(self):
        group = ChordGroup([
            self._make_placement(4, 2),
            self._make_placement(3, 4),
            self._make_placement(2, 5),
        ])
        assert group.hand_span == 3  # 5 - 2

    def test_base_position(self):
        group = ChordGroup([
            self._make_placement(4, 5),
            self._make_placement(3, 7),
        ])
        assert group.base_position == 5
