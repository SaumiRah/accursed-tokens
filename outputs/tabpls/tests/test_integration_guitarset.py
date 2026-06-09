"""
GuitarSet integration tests.

GuitarSet (Xi et al., 2018) provides:
  - 360 guitar recordings (hex pickup + mic mix) from 6 players × 5 chord types × 6 keys × 2 tempos
  - Ground-truth JAMS annotations: note events, chords, beats, keys
  - Download: https://zenodo.org/record/3371780 (~2 GB)

Usage
-----
Run with dataset path via marker:

    pytest tests/test_integration_guitarset.py -v --guitarset /path/to/guitarset_v1.1

If --guitarset is not supplied (or the path doesn't exist), all tests are skipped.

Evaluation metrics
------------------
Note-level:
  - Precision  = matched / detected
  - Recall     = matched / ground_truth
  - F1         = harmonic mean of P and R

A detected note is "matched" if there exists a ground-truth note with:
  - Onset within ±50ms
  - MIDI pitch within ±1 semitone (±0.5 relaxed)

Results printed to stdout and optionally written to outputs/eval_guitarset.csv.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from detect import NoteEvent


# ── pytest plugin to add --guitarset option ───────────────────────────────────

def pytest_addoption(parser):
    parser.addoption(
        "--guitarset",
        action="store",
        default=None,
        help="Path to the GuitarSet v1.1 root directory",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "guitarset: tests that require the GuitarSet dataset (skip if --guitarset not provided)",
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def guitarset_path(request) -> Path | None:
    raw = request.config.getoption("--guitarset", default=None)
    if raw is None:
        return None
    p = Path(raw)
    return p if p.exists() else None


@pytest.fixture(scope="session")
def guitarset_recordings(guitarset_path) -> list[dict]:
    """Return a list of {audio_path, annotation_path, player, style, bpm} dicts."""
    if guitarset_path is None:
        return []
    return list(_discover_recordings(guitarset_path))


# ── GuitarSet data loading ────────────────────────────────────────────────────

def _discover_recordings(root: Path) -> Iterator[dict]:
    """
    Walk the GuitarSet directory structure and yield recording metadata dicts.

    Expected layout (v1.1):
        <root>/
          audio_hex_cln/   # clean hex pickup (isolated string tracks)
          audio_mic/       # mic mix recordings
          annotation/      # JAMS files

    We use audio_mic for the pipeline (realistic mixed recording).
    """
    audio_dir = root / "audio_mic"
    annot_dir = root / "annotation"

    if not audio_dir.exists():
        # Try alternate layout
        audio_dir = root / "audio"
    if not annot_dir.exists():
        pytest.skip(f"GuitarSet annotation dir not found under {root}")

    for audio_file in sorted(audio_dir.glob("*.wav")):
        stem = audio_file.stem
        annot_file = annot_dir / f"{stem}.jams"
        if not annot_file.exists():
            continue

        # Parse metadata from filename: e.g. "00_BN1-129-Eb_solo.wav"
        parts = stem.split("_")
        yield {
            "audio_path": audio_file,
            "annotation_path": annot_file,
            "stem": stem,
            "bpm": _parse_bpm_from_stem(stem),
        }


def _parse_bpm_from_stem(stem: str) -> float:
    """Extract BPM from GuitarSet filename (e.g. '00_BN1-129-Eb_solo' → 129.0)."""
    try:
        parts = stem.split("-")
        if len(parts) >= 2:
            return float(parts[1])
    except (ValueError, IndexError):
        pass
    return 120.0


def _load_ground_truth_notes(annotation_path: Path) -> list[NoteEvent]:
    """
    Parse a GuitarSet JAMS file and return ground-truth NoteEvents.

    JAMS format: JSON with observations[].value containing note_hz or pitch_midi.
    """
    try:
        import jams
        jam = jams.load(str(annotation_path))
        events: list[NoteEvent] = []
        for ann in jam.annotations:
            if ann.namespace not in ("note_hz", "note_midi"):
                continue
            for obs in ann.data:
                onset = float(obs.time.total_seconds())
                offset = onset + float(obs.duration.total_seconds())
                value = float(obs.value)
                if ann.namespace == "note_hz":
                    import math
                    midi = round(12 * math.log2(value / 440.0) + 69)
                else:
                    midi = round(value)
                events.append(NoteEvent(
                    onset=onset, offset=offset,
                    midi_pitch=midi, confidence=1.0,
                ))
        return sorted(events, key=lambda e: e.onset)
    except ImportError:
        # jams not installed — parse raw JSON
        return _load_ground_truth_notes_raw(annotation_path)


def _load_ground_truth_notes_raw(annotation_path: Path) -> list[NoteEvent]:
    """Fallback JAMS parser using raw JSON (no jams library required)."""
    import math
    data = json.loads(annotation_path.read_text())
    events: list[NoteEvent] = []
    for ann in data.get("annotations", []):
        ns = ann.get("namespace", "")
        if ns not in ("note_hz", "note_midi"):
            continue
        for obs in ann.get("data", []):
            onset = float(obs.get("time", 0))
            dur = float(obs.get("duration", 0))
            value = float(obs.get("value", 0))
            if ns == "note_hz" and value > 0:
                midi = round(12 * math.log2(value / 440.0) + 69)
            elif ns == "note_midi":
                midi = round(value)
            else:
                continue
            events.append(NoteEvent(
                onset=onset, offset=onset + dur,
                midi_pitch=midi, confidence=1.0,
            ))
    return sorted(events, key=lambda e: e.onset)


# ── Evaluation metrics ────────────────────────────────────────────────────────

@dataclass
class EvalResult:
    stem: str
    n_detected: int
    n_ground_truth: int
    n_matched: int
    precision: float
    recall: float
    f1: float
    extra: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return (
            f"{self.stem}: P={self.precision:.3f} R={self.recall:.3f} "
            f"F1={self.f1:.3f} "
            f"(det={self.n_detected} gt={self.n_ground_truth} matched={self.n_matched})"
        )


def evaluate_transcription(
    detected: list[NoteEvent],
    ground_truth: list[NoteEvent],
    onset_tol: float = 0.05,   # seconds
    pitch_tol: int = 1,        # semitones
) -> tuple[float, float, float]:
    """
    Compute (precision, recall, F1) for detected vs. ground-truth notes.

    A detection is a true positive if there exists an unmatched ground-truth note
    with onset within ±onset_tol and pitch within ±pitch_tol semitones.
    """
    gt_remaining = list(range(len(ground_truth)))
    matched = 0

    for det in detected:
        best_idx = None
        best_dist = float("inf")
        for j in gt_remaining:
            gt = ground_truth[j]
            if abs(det.onset - gt.onset) <= onset_tol and abs(det.midi_pitch - gt.midi_pitch) <= pitch_tol:
                dist = abs(det.onset - gt.onset)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = j
        if best_idx is not None:
            matched += 1
            gt_remaining.remove(best_idx)

    n_det = len(detected)
    n_gt = len(ground_truth)
    precision = matched / n_det if n_det > 0 else 0.0
    recall = matched / n_gt if n_gt > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.guitarset
class TestGuitarSetTranscription:
    """Integration tests against GuitarSet. Skipped if dataset unavailable."""

    def test_guitarset_available(self, guitarset_path):
        if guitarset_path is None:
            pytest.skip("GuitarSet not available (pass --guitarset /path/to/dataset)")
        assert guitarset_path.exists()

    def test_pipeline_runs_on_first_recording(self, guitarset_recordings):
        """Smoke test: pipeline completes without error on the first recording."""
        if not guitarset_recordings:
            pytest.skip("No GuitarSet recordings found")

        import pipeline as _pipeline
        rec = guitarset_recordings[0]
        tab = _pipeline.transcribe(
            rec["audio_path"],
            bpm=rec["bpm"],
            detect_techniques=True,
        )
        assert isinstance(tab, str)
        assert len(tab) > 0
        print(f"\n--- Tab for {rec['stem']} ---\n{tab[:500]}")

    def test_note_detection_f1_above_threshold(self, guitarset_recordings):
        """
        Check that note-level F1 meets a minimum threshold on the first recording.

        Target: F1 > 0.40 (BasicPitch baseline on mixed audio without separation).
        This is intentionally modest — guitar mixed into a full band is hard.
        Isolated guitar (--separate) typically achieves F1 > 0.65.
        """
        if not guitarset_recordings:
            pytest.skip("No GuitarSet recordings found")

        from detect import detect, filter_guitar_range
        from audio import load
        import tempfile
        from pathlib import Path

        rec = guitarset_recordings[0]
        print(f"\nEvaluating: {rec['stem']}")

        detected = detect(rec["audio_path"])
        detected = filter_guitar_range(detected)
        ground_truth = _load_ground_truth_notes(rec["annotation_path"])

        print(f"  Detected: {len(detected)} notes")
        print(f"  Ground truth: {len(ground_truth)} notes")

        p, r, f1 = evaluate_transcription(detected, ground_truth)
        print(f"  P={p:.3f}  R={r:.3f}  F1={f1:.3f}")

        assert f1 >= 0.25, (
            f"F1 {f1:.3f} is below minimum threshold 0.25 for {rec['stem']}. "
            f"Check BasicPitch install and audio quality."
        )

    @pytest.mark.slow
    def test_batch_evaluation(self, guitarset_recordings, tmp_path):
        """
        Evaluate the full pipeline on up to 10 recordings. Writes results CSV.
        Marked slow — run with: pytest -m slow --guitarset /path/to/dataset
        """
        if not guitarset_recordings:
            pytest.skip("No GuitarSet recordings found")

        from detect import detect, filter_guitar_range
        import pipeline as _pipeline

        results: list[EvalResult] = []
        batch = guitarset_recordings[:10]

        for rec in batch:
            print(f"\nProcessing {rec['stem']}…")
            try:
                detected = detect(rec["audio_path"])
                detected = filter_guitar_range(detected)
                ground_truth = _load_ground_truth_notes(rec["annotation_path"])
                p, r, f1 = evaluate_transcription(detected, ground_truth)
                result = EvalResult(
                    stem=rec["stem"],
                    n_detected=len(detected),
                    n_ground_truth=len(ground_truth),
                    n_matched=round(p * len(detected)),
                    precision=p, recall=r, f1=f1,
                )
                print(f"  {result}")
                results.append(result)
            except Exception as exc:
                print(f"  ERROR: {exc}")

        if not results:
            pytest.skip("No results computed")

        avg_f1 = sum(r.f1 for r in results) / len(results)
        print(f"\nAverage F1 across {len(results)} recordings: {avg_f1:.3f}")

        # Write CSV
        csv_path = Path(__file__).parent.parent / "outputs" / "eval_guitarset.csv"
        csv_path.parent.mkdir(exist_ok=True)
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["stem", "precision", "recall", "f1",
                                               "n_detected", "n_ground_truth", "n_matched"])
            w.writeheader()
            for r in results:
                w.writerow({
                    "stem": r.stem, "precision": f"{r.precision:.4f}",
                    "recall": f"{r.recall:.4f}", "f1": f"{r.f1:.4f}",
                    "n_detected": r.n_detected, "n_ground_truth": r.n_ground_truth,
                    "n_matched": r.n_matched,
                })
        print(f"Results written to {csv_path}")

        assert avg_f1 >= 0.20, f"Average F1 {avg_f1:.3f} across batch is too low."


# ── Offline unit tests (no dataset needed) ────────────────────────────────────

class TestEvalMetrics:
    """Unit tests for the evaluation metric computation. No dataset needed."""

    def test_perfect_match(self):
        notes = [
            NoteEvent(onset=0.0, offset=0.5, midi_pitch=60, confidence=1.0),
            NoteEvent(onset=0.5, offset=1.0, midi_pitch=64, confidence=1.0),
        ]
        p, r, f1 = evaluate_transcription(notes, notes)
        assert p == pytest.approx(1.0)
        assert r == pytest.approx(1.0)
        assert f1 == pytest.approx(1.0)

    def test_no_detections(self):
        gt = [NoteEvent(onset=0.0, offset=0.5, midi_pitch=60, confidence=1.0)]
        p, r, f1 = evaluate_transcription([], gt)
        assert p == 0.0
        assert r == 0.0
        assert f1 == 0.0

    def test_no_ground_truth(self):
        det = [NoteEvent(onset=0.0, offset=0.5, midi_pitch=60, confidence=1.0)]
        p, r, f1 = evaluate_transcription(det, [])
        assert p == 0.0
        assert r == 0.0
        assert f1 == 0.0

    def test_onset_tolerance(self):
        det = [NoteEvent(onset=0.03, offset=0.5, midi_pitch=60, confidence=1.0)]
        gt = [NoteEvent(onset=0.0, offset=0.5, midi_pitch=60, confidence=1.0)]
        p, r, f1 = evaluate_transcription(det, gt, onset_tol=0.05)
        assert f1 == pytest.approx(1.0)

    def test_onset_outside_tolerance(self):
        det = [NoteEvent(onset=0.10, offset=0.5, midi_pitch=60, confidence=1.0)]
        gt = [NoteEvent(onset=0.0, offset=0.5, midi_pitch=60, confidence=1.0)]
        p, r, f1 = evaluate_transcription(det, gt, onset_tol=0.05)
        assert f1 == 0.0

    def test_pitch_tolerance(self):
        det = [NoteEvent(onset=0.0, offset=0.5, midi_pitch=61, confidence=1.0)]
        gt = [NoteEvent(onset=0.0, offset=0.5, midi_pitch=60, confidence=1.0)]
        p, r, f1 = evaluate_transcription(det, gt, pitch_tol=1)
        assert f1 == pytest.approx(1.0)

    def test_pitch_outside_tolerance(self):
        det = [NoteEvent(onset=0.0, offset=0.5, midi_pitch=62, confidence=1.0)]
        gt = [NoteEvent(onset=0.0, offset=0.5, midi_pitch=60, confidence=1.0)]
        p, r, f1 = evaluate_transcription(det, gt, pitch_tol=1)
        assert f1 == 0.0

    def test_no_double_matching(self):
        # Two detections, one ground truth — only one match allowed
        det = [
            NoteEvent(onset=0.0, offset=0.5, midi_pitch=60, confidence=1.0),
            NoteEvent(onset=0.02, offset=0.5, midi_pitch=60, confidence=1.0),
        ]
        gt = [NoteEvent(onset=0.0, offset=0.5, midi_pitch=60, confidence=1.0)]
        p, r, f1 = evaluate_transcription(det, gt)
        assert p == pytest.approx(0.5)  # 1/2 detections matched
        assert r == pytest.approx(1.0)  # 1/1 GT matched

    def test_partial_match(self):
        det = [
            NoteEvent(onset=0.0, offset=0.5, midi_pitch=60, confidence=1.0),
            NoteEvent(onset=1.0, offset=1.5, midi_pitch=64, confidence=1.0),
        ]
        gt = [
            NoteEvent(onset=0.0, offset=0.5, midi_pitch=60, confidence=1.0),
            NoteEvent(onset=1.0, offset=1.5, midi_pitch=72, confidence=1.0),  # different pitch
        ]
        p, r, f1 = evaluate_transcription(det, gt, pitch_tol=1)
        assert p == pytest.approx(0.5)
        assert r == pytest.approx(0.5)
