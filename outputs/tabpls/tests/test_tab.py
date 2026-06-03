"""
Unit tests for the tab renderer.

Run: pytest tests/test_tab.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fretboard import Placement, ChordGroup
from tab import render, render_compact, STRING_LABELS, N_STRINGS


def _make_group(notes: list[tuple[int, int]], onset: float = 0.0) -> ChordGroup:
    """Helper: (string, fret) tuples → ChordGroup."""
    placements = [
        Placement(
            onset=onset, offset=onset + 0.4,
            midi_pitch=40,
            string=s, fret=f, confidence=0.9,
        )
        for s, f in notes
    ]
    return ChordGroup(placements=placements)


class TestRenderCompact:
    def test_empty(self):
        result = render_compact([])
        assert result == "(no notes)"

    def test_single_open_string(self):
        group = _make_group([(1, 0)])  # high e, open
        result = render_compact([group])
        lines = result.splitlines()
        assert len(lines) == N_STRINGS
        # First line (high e) should contain "0"
        assert "0" in lines[0]

    def test_six_string_chord(self):
        # E major open chord
        group = _make_group([(6, 0), (5, 2), (4, 2), (3, 1), (2, 0), (1, 0)])
        result = render_compact([group])
        lines = result.splitlines()
        assert len(lines) == N_STRINGS
        # Check string labels
        for i, label in enumerate(STRING_LABELS):
            assert lines[i].startswith(label + "|")

    def test_high_fret_number(self):
        group = _make_group([(1, 15)])  # 2-digit fret
        result = render_compact([group])
        assert "15" in result

    def test_multiple_groups(self):
        g1 = _make_group([(1, 0)], onset=0.0)
        g2 = _make_group([(1, 3)], onset=0.5)
        result = render_compact([g1, g2])
        assert "0" in result
        assert "3" in result

    def test_output_has_bar_separators(self):
        group = _make_group([(3, 5)])
        result = render_compact([group])
        for line in result.splitlines():
            assert line.count("|") >= 2


class TestRender:
    def test_empty(self):
        result = render([])
        assert result == "(no notes)"

    def test_output_has_n_strings_lines(self):
        group = _make_group([(1, 0)], onset=0.0)
        result = render([group], total_duration=2.0, bpm=120.0)
        # Each row has N_STRINGS lines; multiple rows are separated by blank lines
        rows = result.split("\n\n")
        for row in rows:
            lines = row.splitlines()
            assert len(lines) == N_STRINGS

    def test_string_labels_present(self):
        group = _make_group([(2, 3)], onset=0.0)
        result = render([group], total_duration=4.0, bpm=120.0)
        for label in STRING_LABELS:
            assert label in result

    def test_fret_number_appears_in_output(self):
        group = _make_group([(3, 7)], onset=0.0)
        result = render([group], total_duration=4.0, bpm=120.0)
        assert "7" in result

    def test_multiple_measures(self):
        # Place notes spread across 2 measures (each = 2s at 120bpm, 4/4)
        g1 = _make_group([(1, 0)], onset=0.0)
        g2 = _make_group([(1, 5)], onset=2.5)
        result = render([g1, g2], total_duration=5.0, bpm=120.0)
        # At least two bar separators in each line
        first_line = result.splitlines()[0]
        assert first_line.count("|") >= 3  # open + at least 1 internal + close
