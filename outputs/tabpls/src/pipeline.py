"""
TabPls — end-to-end transcription pipeline.

Usage:
    from pipeline import transcribe
    tab_text = transcribe("my_song.mp3")
    print(tab_text)

CLI:
    python pipeline.py transcribe my_song.mp3
    python pipeline.py transcribe my_song.mp3 --separate --bpm 95 --tuning drop_d
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import audio as _audio
import detect as _detect
import fretboard as _fb
import tab as _tab
import techniques as _tech


def transcribe(
    input_path: str | Path,
    *,
    separate: bool = False,
    tuning: str = "standard",
    onset_threshold: float = 0.50,
    bpm: float = 120.0,
    time_sig: tuple[int, int] = (4, 4),
    compact: bool = False,
    detect_techniques: bool = True,
    device: str = "cpu",
    out_wav: str | Path | None = None,
) -> str:
    """
    Transcribe a guitar audio file and return ASCII tab.

    Args:
        input_path: Path to audio file (.mp3, .wav, .flac, …).
        separate: If True, run Demucs source separation to isolate guitar first.
        tuning: Guitar tuning ('standard', 'drop_d', 'open_g', …).
        onset_threshold: BasicPitch onset confidence threshold (0–1).
        bpm: Song tempo in BPM (for rhythmic quantization).
        time_sig: Time signature as (beats_per_bar, beat_value).
        compact: If True, use compact (non-quantized) rendering.
        device: 'cpu' or 'cuda' (for Demucs source separation).
        out_wav: If set, save the preprocessed (or separated) guitar audio here.

    Returns:
        ASCII guitar tab string.
    """
    input_path = Path(input_path)

    # Step 1: Source separation (optional)
    if separate:
        print(f"[tabpls] Separating guitar stem from {input_path.name}…", file=sys.stderr)
        guitar_path = _audio.separate_guitar(input_path, device=device)
        print(f"[tabpls] Guitar stem: {guitar_path}", file=sys.stderr)
    else:
        guitar_path = input_path

    # Step 2: Load and normalize audio
    print("[tabpls] Loading audio…", file=sys.stderr)
    waveform, sr = _audio.load(guitar_path)
    total_duration = len(waveform) / sr
    print(f"[tabpls] Duration: {total_duration:.1f}s @ {sr}Hz", file=sys.stderr)

    # Optionally save the preprocessed audio
    if out_wav:
        _audio.save(waveform, sr, out_wav)
        print(f"[tabpls] Preprocessed audio saved to {out_wav}", file=sys.stderr)

    # Save to temp file for BasicPitch (it expects a path, not a numpy array)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    _audio.save(waveform, sr, tmp_path)

    # Step 3: Note detection
    print("[tabpls] Detecting notes (BasicPitch)…", file=sys.stderr)
    events = _detect.detect(tmp_path, onset_threshold=onset_threshold)
    tmp_path.unlink(missing_ok=True)

    # Filter to guitar pitch range
    events = _detect.filter_guitar_range(events)
    print(f"[tabpls] Detected {len(events)} notes in guitar range.", file=sys.stderr)

    if not events:
        return "(no guitar notes detected — try lowering onset_threshold or using --separate)"

    # Step 4: Fretboard mapping
    print("[tabpls] Mapping to fretboard…", file=sys.stderr)
    chord_groups = _fb.place(events, tuning=tuning)
    print(f"[tabpls] {len(chord_groups)} chord groups placed.", file=sys.stderr)

    # Step 4b: Technique detection (optional)
    if detect_techniques:
        _tech.annotate(chord_groups)
        print("[tabpls] Technique detection complete.", file=sys.stderr)

    # Step 5: Render
    if compact:
        return _tab.render_compact(chord_groups, bpm=bpm)
    return _tab.render(chord_groups, total_duration=total_duration, bpm=bpm, time_sig=time_sig)


def _cli() -> None:
    parser = argparse.ArgumentParser(
        prog="tabpls",
        description="Transcribe guitar audio to ASCII tab.",
    )
    sub = parser.add_subparsers(dest="command")

    t = sub.add_parser("transcribe", help="Transcribe an audio file to guitar tab.")
    t.add_argument("input", help="Audio file path (.mp3, .wav, .flac, …)")
    t.add_argument("--separate", action="store_true", help="Run Demucs source separation first")
    t.add_argument("--tuning", default="standard", choices=list(_fb.TUNINGS), help="Guitar tuning")
    t.add_argument("--onset-threshold", type=float, default=0.50, metavar="THRESH",
                   help="BasicPitch onset confidence threshold (0–1, default 0.50)")
    t.add_argument("--bpm", type=float, default=120.0, help="Song tempo in BPM (default 120)")
    t.add_argument("--compact", action="store_true", help="Use compact non-quantized rendering")
    t.add_argument("--no-techniques", action="store_true", help="Disable technique detection (h/p/b/~)")
    t.add_argument("--device", default="cpu", help="Device for Demucs: cpu or cuda")
    t.add_argument("--out", metavar="FILE", help="Write tab to FILE instead of stdout")
    t.add_argument("--out-wav", metavar="WAV", help="Save preprocessed guitar audio to WAV")

    args = parser.parse_args()

    if args.command == "transcribe":
        tab_text = transcribe(
            args.input,
            separate=args.separate,
            tuning=args.tuning,
            onset_threshold=args.onset_threshold,
            bpm=args.bpm,
            compact=args.compact,
            detect_techniques=not args.no_techniques,
            device=args.device,
            out_wav=args.out_wav,
        )
        if args.out:
            Path(args.out).write_text(tab_text)
            print(f"Tab written to {args.out}", file=sys.stderr)
        else:
            print(tab_text)
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
