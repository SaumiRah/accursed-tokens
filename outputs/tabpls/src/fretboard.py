"""
Fretboard mapper: assigns guitar (string, fret) placements to MIDI note events.

Uses Viterbi dynamic programming to minimize a cost function that penalizes
large hand-position shifts and unplayable stretches across consecutive notes
and chords.

Standard tuning is the default; alternate tunings are supported via TUNINGS.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from detect import NoteEvent

# ── Guitar constants ──────────────────────────────────────────────────────────

# Open-string MIDI pitches in standard tuning (string 1 = high E, 6 = low E).
# Index 0 = string 1 (highest), index 5 = string 6 (lowest).
STANDARD_TUNING = (64, 59, 55, 50, 45, 40)  # e B G D A E

TUNINGS: dict[str, tuple[int, ...]] = {
    "standard":    (64, 59, 55, 50, 45, 40),
    "drop_d":      (64, 59, 55, 50, 45, 38),
    "open_g":      (62, 59, 55, 50, 43, 38),
    "open_e":      (64, 59, 56, 52, 47, 40),
    "half_step":   (63, 58, 54, 49, 44, 39),
    "full_step":   (62, 57, 53, 48, 43, 38),
}

MAX_FRET = 22       # practical maximum fret
MAX_SPAN = 4        # maximum comfortable fret span within one hand position
CHORD_WINDOW = 0.05 # seconds: notes this close in onset are treated as a chord

# ── Costs ─────────────────────────────────────────────────────────────────────

COST_SHIFT_PER_FRET = 1.0     # penalty per fret of hand position movement
COST_UNPLAYABLE = 1000.0      # heavy penalty for span > MAX_SPAN
COST_HIGH_FRET = 0.2          # mild penalty per fret above fret 12 (thin tone)
COST_OPEN_STRING_BONUS = -0.5 # slight reward for open string (natural, sustained)


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class Placement:
    """A single note with its assigned string/fret position."""
    onset: float
    offset: float
    midi_pitch: int
    string: int          # 1 (high E) to 6 (low E)
    fret: int            # 0 = open, 1–MAX_FRET
    confidence: float
    pitch_bends: list[float] = field(default_factory=list)

    @property
    def is_open(self) -> bool:
        return self.fret == 0

    def hand_position(self) -> int:
        """Index finger position: open string = 0, else the fret itself."""
        return 0 if self.fret == 0 else self.fret


@dataclass
class ChordGroup:
    """Notes that should be played simultaneously (close onset times)."""
    placements: list[Placement]

    @property
    def onset(self) -> float:
        return min(p.onset for p in self.placements)

    @property
    def hand_span(self) -> int:
        frets = [p.fret for p in self.placements if not p.is_open]
        if not frets:
            return 0
        return max(frets) - min(frets)

    @property
    def base_position(self) -> int:
        frets = [p.fret for p in self.placements if not p.is_open]
        return min(frets) if frets else 0


# ── Candidate generation ──────────────────────────────────────────────────────

def _candidates(midi_pitch: int, tuning: tuple[int, ...]) -> list[tuple[int, int]]:
    """Return all (string_idx_0based, fret) pairs for this MIDI pitch."""
    result = []
    for s, open_midi in enumerate(tuning):
        fret = midi_pitch - open_midi
        if 0 <= fret <= MAX_FRET:
            result.append((s, fret))
    return result


# ── Cost functions ────────────────────────────────────────────────────────────

def _note_cost(fret: int, prev_pos: int) -> float:
    shift = abs(fret - prev_pos) if fret > 0 else 0
    high = max(0, fret - 12) * COST_HIGH_FRET
    bonus = COST_OPEN_STRING_BONUS if fret == 0 else 0.0
    return COST_SHIFT_PER_FRET * shift + high + bonus


def _chord_cost(placements: list[tuple[int, int]], prev_pos: int) -> float:
    """Cost for a simultaneous chord given previous hand position."""
    frets = [f for _, f in placements if f > 0]
    if not frets:
        return 0.0
    lo, hi = min(frets), max(frets)
    span_penalty = max(0, hi - lo - MAX_SPAN) * COST_UNPLAYABLE
    shift = abs(lo - prev_pos) * COST_SHIFT_PER_FRET
    high = max(0, hi - 12) * COST_HIGH_FRET
    return span_penalty + shift + high


# ── Grouping notes into time steps ────────────────────────────────────────────

def _group_by_onset(events: Sequence[NoteEvent]) -> list[list[NoteEvent]]:
    """
    Group notes whose onset times are within CHORD_WINDOW of each other.
    Returns a list of groups, each sorted by onset.
    """
    if not events:
        return []
    sorted_events = sorted(events, key=lambda e: e.onset)
    groups: list[list[NoteEvent]] = [[sorted_events[0]]]
    for ev in sorted_events[1:]:
        if ev.onset - groups[-1][0].onset <= CHORD_WINDOW:
            groups[-1].append(ev)
        else:
            groups.append([ev])
    return groups


# ── Viterbi DP ────────────────────────────────────────────────────────────────

def place(
    events: Sequence[NoteEvent],
    tuning: str | tuple[int, ...] = "standard",
) -> list[ChordGroup]:
    """
    Assign (string, fret) positions to all note events via Viterbi DP.

    Args:
        events: Detected note events from the AMT stage.
        tuning: Guitar tuning name (see TUNINGS) or a 6-tuple of open-string MIDI pitches.

    Returns:
        List of ChordGroups in onset order, each containing Placement objects
        with string/fret assignments.
    """
    if isinstance(tuning, str):
        open_strings = TUNINGS[tuning]
    else:
        open_strings = tuning

    groups = _group_by_onset(events)
    if not groups:
        return []

    # Each DP state is the current hand position (int).
    # We track the best (cost, backpointer) for each (group_idx, candidate_combo).

    # For memory efficiency we only keep the previous layer's best cost per state.
    # State = hand position (0 = open position, 1–MAX_FRET = fretted).

    INF = math.inf
    n_states = MAX_FRET + 1  # positions 0..MAX_FRET

    # prev_costs[pos] = minimum cost to reach this hand position after processing prev group
    prev_costs = [0.0] * n_states
    # backpointers: list of (group_idx → best_combo_for_each_state)
    # We store full per-group assignment for backtracking.
    # assignments[group_idx][pos] = list of (string, fret) for each note in that group
    best_assignments: list[list[list[tuple[int, int]] | None]] = []

    for group in groups:
        # Generate all candidate combos for this group (cross product of per-note candidates)
        # For chords, we need to pick one candidate per note without reusing strings.
        per_note_cands = [_candidates(e.midi_pitch, open_strings) for e in group]

        # Build valid combos (no string reuse)
        def _combos(remaining: list[list[tuple[int, int]]], used_strings: set[int]) -> list[list[tuple[int, int]]]:
            if not remaining:
                return [[]]
            result = []
            for s, f in remaining[0]:
                if s not in used_strings:
                    for rest in _combos(remaining[1:], used_strings | {s}):
                        result.append([(s, f)] + rest)
            return result

        valid_combos = _combos(per_note_cands, set())
        if not valid_combos:
            # Fallback: allow string reuse (shouldn't happen in practice)
            valid_combos = [[c[0]] for c in per_note_cands]

        # DP step
        curr_costs = [INF] * n_states
        curr_best_combo: list[list[tuple[int, int]] | None] = [None] * n_states

        for combo in valid_combos:
            frets = [f for _, f in combo]
            non_open = [f for f in frets if f > 0]
            hand_pos = min(non_open) if non_open else 0
            chord_extra = _chord_cost(combo, hand_pos)

            for prev_pos in range(n_states):
                base = prev_costs[prev_pos]
                if base == INF:
                    continue
                shift = abs(hand_pos - prev_pos) * COST_SHIFT_PER_FRET
                total = base + shift + chord_extra
                if total < curr_costs[hand_pos]:
                    curr_costs[hand_pos] = total
                    curr_best_combo[hand_pos] = combo

        best_assignments.append(curr_best_combo)
        prev_costs = curr_costs

    # Backtrack: find best final state
    best_final_pos = min(range(n_states), key=lambda p: prev_costs[p])

    # Rebuild assignments forward (simpler than actual backtracking for this structure)
    # Re-run forward pass collecting the chosen combo per group.
    # For simplicity, pick the globally best combo at each group given the final position.
    # (A full backtrack would require storing prev_pos pointers — left as a Phase 2 improvement.)
    result_groups: list[ChordGroup] = []
    prev_pos = 0
    for g_idx, (group, cand_combos_by_state) in enumerate(zip(groups, best_assignments)):
        combo = cand_combos_by_state[best_final_pos]
        if combo is None:
            # Fallback: use the cheapest candidate for each note independently
            combo = [cands[0] if cands else (0, 0) for cands in [_candidates(e.midi_pitch, open_strings) for e in group]]

        placements = []
        for (s_idx, fret), ev in zip(combo, group):
            placements.append(Placement(
                onset=ev.onset,
                offset=ev.offset,
                midi_pitch=ev.midi_pitch,
                string=s_idx + 1,  # 1-indexed
                fret=fret,
                confidence=ev.confidence,
                pitch_bends=ev.pitch_bends,
            ))
        result_groups.append(ChordGroup(placements=placements))

    return result_groups
