"""
Tab renderer: converts ChordGroups (placed notes) into ASCII guitar tab.

Output format:
  e|---0---3---5---|
  B|---1---3---5---|
  G|---0---2---5---|
  D|---2---0---3---|
  A|---2-------3---|
  E|---0-------1---|

String labels match standard EADGBE from high (string 1, e) to low (string 6, E).
"""

from __future__ import annotations

import math
from typing import Sequence

from fretboard import ChordGroup, Placement

# String labels, index 0 = string 1 (high e), index 5 = string 6 (low E)
STRING_LABELS = ["e", "B", "G", "D", "A", "E"]
N_STRINGS = 6

# Column widths
MIN_COL_WIDTH = 4      # characters per time slot (e.g. "---0" or "----")
BEATS_PER_MEASURE = 4  # default 4/4 time

# Gap character
GAP = "-"
BAR_SEP = "|"


def _fret_str(fret: int) -> str:
    """Format fret number as a string (0–9 are 1-char, 10+ are 2-char)."""
    return str(fret)


def _measure_lines(
    slots: list[dict[int, int]],  # list of {string_1based → fret} per time slot
    col_width: int,
) -> list[str]:
    """Render one measure as 6 tab lines."""
    lines = ["" for _ in range(N_STRINGS)]
    for slot in slots:
        for s_idx in range(N_STRINGS):
            string_num = s_idx + 1  # 1-indexed
            if string_num in slot:
                fret_s = _fret_str(slot[string_num])
                padding = GAP * (col_width - len(fret_s) - 1)
                lines[s_idx] += GAP + padding + fret_s
            else:
                lines[s_idx] += GAP * col_width
    return lines


def render(
    chord_groups: Sequence[ChordGroup],
    total_duration: float | None = None,
    bpm: float = 120.0,
    time_sig: tuple[int, int] = (4, 4),
    measures_per_row: int = 4,
) -> str:
    """
    Render ChordGroups as an ASCII guitar tab string.

    Args:
        chord_groups: Placed note groups from fretboard.place().
        total_duration: Total audio duration in seconds (used to set the last bar).
        bpm: Tempo in beats per minute (affects column width / quantization).
        time_sig: (numerator, denominator) — default (4, 4).
        measures_per_row: How many measures to print per line of tab.

    Returns:
        Multi-line ASCII tab string.
    """
    if not chord_groups:
        return "(no notes)"

    beats, beat_denom = time_sig
    beat_duration = 60.0 / bpm                     # seconds per beat
    measure_duration = beat_duration * beats        # seconds per measure

    if total_duration is None:
        total_duration = max(
            p.offset for g in chord_groups for p in g.placements
        ) + measure_duration

    n_measures = math.ceil(total_duration / measure_duration)
    slots_per_measure = beats * (16 // beat_denom)  # 16th-note grid slots per measure
    slot_duration = measure_duration / slots_per_measure

    # Build measure → slot → {string → fret} mapping
    measure_slots: list[list[dict[int, int]]] = [
        [{} for _ in range(slots_per_measure)] for _ in range(n_measures)
    ]

    for group in chord_groups:
        t = group.onset
        measure_idx = int(t / measure_duration)
        slot_idx = int((t % measure_duration) / slot_duration)
        measure_idx = min(measure_idx, n_measures - 1)
        slot_idx = min(slot_idx, slots_per_measure - 1)
        for p in group.placements:
            measure_slots[measure_idx][slot_idx][p.string] = p.fret

    # Determine max fret width for column sizing
    all_frets = [
        p.fret for g in chord_groups for p in g.placements
    ]
    max_fret_chars = max(len(_fret_str(f)) for f in all_frets) if all_frets else 1
    col_width = max(MIN_COL_WIDTH, max_fret_chars + 2)

    output_rows: list[str] = []

    for row_start in range(0, n_measures, measures_per_row):
        row_end = min(row_start + measures_per_row, n_measures)
        row_lines = ["" for _ in range(N_STRINGS)]

        # Open bar line
        for s_idx in range(N_STRINGS):
            row_lines[s_idx] = STRING_LABELS[s_idx] + BAR_SEP

        for m_idx in range(row_start, row_end):
            slots = measure_slots[m_idx]
            m_lines = _measure_lines(slots, col_width)
            for s_idx in range(N_STRINGS):
                row_lines[s_idx] += m_lines[s_idx] + BAR_SEP

        output_rows.append("\n".join(row_lines))

    return "\n\n".join(output_rows)


def render_compact(
    chord_groups: Sequence[ChordGroup],
    bpm: float = 120.0,
) -> str:
    """
    Compact render: one chord per column, no time quantization.
    Useful for quick inspection. Timing is only approximate.
    """
    if not chord_groups:
        return "(no notes)"

    lines = [STRING_LABELS[s] + BAR_SEP for s in range(N_STRINGS)]

    for group in chord_groups:
        fret_map = {p.string: p.fret for p in group.placements}
        cells = []
        for s_idx in range(N_STRINGS):
            s = s_idx + 1
            cells.append(_fret_str(fret_map[s]) if s in fret_map else GAP)
        max_len = max(len(c) for c in cells)
        for s_idx in range(N_STRINGS):
            pad = GAP * (max_len - len(cells[s_idx]))
            lines[s_idx] += GAP + pad + cells[s_idx]

    for s_idx in range(N_STRINGS):
        lines[s_idx] += BAR_SEP

    return "\n".join(lines)
