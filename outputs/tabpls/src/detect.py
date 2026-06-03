"""
Note detection via BasicPitch (Spotify AMT model).

Wraps BasicPitch to produce a list of NoteEvent objects — the currency used
throughout the TabPls pipeline before fretboard mapping.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


@dataclass
class NoteEvent:
    """A single detected note (pitch + timing, before fretboard placement)."""
    onset: float       # seconds
    offset: float      # seconds
    midi_pitch: int    # 0–127
    confidence: float  # 0.0–1.0
    pitch_bends: list[float] = field(default_factory=list)  # semitones, per-frame

    @property
    def duration(self) -> float:
        return self.offset - self.onset


def detect(
    audio_path: str | Path,
    onset_threshold: float = 0.50,
    frame_threshold: float = 0.30,
    minimum_note_length: float = 0.058,  # seconds (~1 frame at 22050/512)
    minimum_freq: float | None = 32.7,   # C1 — below lowest guitar note
    maximum_freq: float | None = 2093.0, # C7 — above practical guitar range
    multiple_pitch_bends: bool = False,
) -> list[NoteEvent]:
    """
    Run BasicPitch on an audio file and return detected NoteEvents.

    Args:
        audio_path: Path to the (optionally guitar-isolated) audio file.
        onset_threshold: Confidence threshold for note onset detection (0–1).
            Lower = more notes detected (noisier); higher = fewer (cleaner).
        frame_threshold: Confidence threshold for active pitch frames.
        minimum_note_length: Shortest allowed note, in seconds.
        minimum_freq: Discard notes below this frequency (Hz). Set to ~82 Hz
            (low E string) for guitar-only transcription.
        maximum_freq: Discard notes above this frequency (Hz).
        multiple_pitch_bends: If True, allow per-note pitch bend data to be
            returned (useful for technique detection later).

    Returns:
        List of NoteEvent sorted by onset time.
    """
    try:
        from basic_pitch.inference import predict
        from basic_pitch import ICASSP_2022_MODEL_PATH
    except ImportError as exc:
        raise ImportError(
            "BasicPitch is required for note detection. "
            "Install it with: pip install basic-pitch"
        ) from exc

    audio_path = Path(audio_path)
    _, _, note_events = predict(
        audio_path,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length=minimum_note_length,
        minimum_frequency=minimum_freq,
        maximum_frequency=maximum_freq,
        multiple_pitch_bends=multiple_pitch_bends,
    )

    events: list[NoteEvent] = []
    for event in note_events:
        # BasicPitch note_events: (start_time, end_time, pitch_midi, amplitude, pitch_bends)
        start, end, pitch, amp, bends = event
        events.append(NoteEvent(
            onset=float(start),
            offset=float(end),
            midi_pitch=int(pitch),
            confidence=float(amp),
            pitch_bends=list(bends) if bends is not None else [],
        ))

    events.sort(key=lambda e: e.onset)
    return events


def filter_guitar_range(events: Sequence[NoteEvent]) -> list[NoteEvent]:
    """
    Keep only notes within the standard guitar pitch range (E2–E6, MIDI 40–88).
    Useful as a post-processing step when the source audio wasn't isolated.
    """
    return [e for e in events if 40 <= e.midi_pitch <= 88]
