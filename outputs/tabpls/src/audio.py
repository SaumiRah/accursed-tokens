"""
Audio loading and preprocessing for TabPls.

Provides utilities to load an audio file, optionally isolate the guitar stem
using Demucs, and export normalized mono audio suitable for AMT (BasicPitch).
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

# BasicPitch expects 22050 Hz mono
TARGET_SR = 22050


def load(path: str | Path, sr: int = TARGET_SR) -> tuple[np.ndarray, int]:
    """
    Load an audio file and return (mono_waveform, sample_rate).

    Resamples to `sr` and converts to mono. Normalizes peak amplitude to 0.95.
    """
    path = Path(path)
    audio, file_sr = librosa.load(str(path), sr=sr, mono=True)
    peak = np.abs(audio).max()
    if peak > 0:
        audio = audio * (0.95 / peak)
    return audio, sr


def separate_guitar(
    path: str | Path,
    out_dir: str | Path | None = None,
    device: str = "cpu",
) -> Path:
    """
    Run Demucs htdemucs_6s source separation and return the path to the guitar stem.

    Requires `demucs` to be installed (`pip install demucs`).

    Args:
        path: Input audio file (mp3, wav, flac, …)
        out_dir: Directory to write separated stems. Uses a temp dir if None.
        device: 'cpu' or 'cuda'.

    Returns:
        Path to the separated guitar stem (wav).
    """
    path = Path(path)
    if out_dir is None:
        out_dir = Path(tempfile.mkdtemp())
    else:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python", "-m", "demucs",
        "--two-stems=guitar",
        "--model", "htdemucs_6s",
        "--device", device,
        "--out", str(out_dir),
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    # Demucs writes to out_dir/htdemucs_6s/{stem_name}/guitar.wav
    stem_path = out_dir / "htdemucs_6s" / path.stem / "guitar.wav"
    if not stem_path.exists():
        raise FileNotFoundError(
            f"Demucs did not produce expected guitar stem at {stem_path}"
        )
    return stem_path


def save(audio: np.ndarray, sr: int, path: str | Path) -> Path:
    """Save a waveform to a .wav file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sr)
    return path
