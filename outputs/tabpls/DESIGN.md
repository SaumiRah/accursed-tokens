# TabPls — Technical Design Document

> Automatic guitar tablature transcription from audio.
> Version: 0.1 (session 2026-06-03)

---

## 1. Problem Statement

Given an audio file containing a guitar performance, generate accurate guitar tablature
(tab): a notation that shows which string and fret to play, rather than abstract musical
pitch. Tab is what guitarists actually use to learn songs.

**Why this is hard:**
- Any given musical pitch can be played on multiple (string, fret) combinations on a guitar.
- Songs are polyphonic: multiple notes played simultaneously.
- Real recordings mix guitar with other instruments.
- Guitar technique adds pitch bends, slides, hammer-ons, pull-offs — expressive details that
  alter perceived pitch without corresponding to a discrete new note.

**Why existing tools fall short:**
- *Ultimate Guitar / Songsterr*: Human-authored tabs; slow, inconsistent quality, large catalog
  but locked behind subscriptions.
- *Chordify*: Detects chord changes, not individual string/fret positions.
- *BasicPitch (Spotify)*: Excellent multi-pitch AMT (automatic music transcription) → MIDI,
  but MIDI ≠ guitar tab. No fretboard mapping.
- *Transcribe!*: Loop-and-slow tool for manual transcription; not automatic.

**Our niche:** End-to-end pipeline — audio in, guitar tab out — with guitar-specific fretboard
placement logic and optional source separation to isolate the guitar track.

---

## 2. System Architecture

```
Input Audio
    │
    ▼
┌─────────────────────┐
│  Source Separation  │  (optional — Demucs)
│  isolate guitar     │
└────────┬────────────┘
         │  guitar stem
         ▼
┌─────────────────────┐
│  Audio Preprocessing│  CQT, resampling, normalization
└────────┬────────────┘
         │  spectrogram / waveform
         ▼
┌─────────────────────┐
│  Note Detection     │  BasicPitch → (onset, offset, pitch, confidence)
│  (AMT)              │
└────────┬────────────┘
         │  note events: [(t_on, t_off, midi_pitch, conf), ...]
         ▼
┌─────────────────────┐
│  Fretboard Mapper   │  DP-based (string, fret) assignment
└────────┬────────────┘
         │  placed notes: [(t_on, t_off, string, fret, technique), ...]
         ▼
┌─────────────────────┐
│  Tab Renderer       │  ASCII tab / MusicXML / Guitar Pro (.gp)
└────────┬────────────┘
         │
         ▼
    Guitar Tab Output
```

### Component responsibilities

| Component | Input | Output | Key decisions |
|---|---|---|---|
| Source separation | Stereo mix | Guitar stem | Use Demucs `htdemucs_6s`; skip if already isolated |
| AMT | Audio | MIDI note events | BasicPitch v0.4+ (Spotify); tunable confidence threshold |
| Fretboard mapper | MIDI notes | (string, fret, technique) | DP with position cost + stretch cost |
| Tab renderer | Placed notes | Text / file | ASCII tab for v1; Guitar Pro for v2 |

---

## 3. Guitar Theory Constraints

### Standard tuning (EADGBE)

| String | MIDI note | Note name |
|--------|-----------|-----------|
| 6 (low E)  | 40 | E2 |
| 5 (A)       | 45 | A2 |
| 4 (D)       | 50 | D3 |
| 3 (G)       | 55 | G3 |
| 2 (B)       | 59 | B3 |
| 1 (high E)  | 64 | E4 |

Fret n on string s raises pitch by n semitones above the open-string note.

**Playable range:** frets 0–24 (most guitars), typically 0–22 practical.
**Max fret span per chord:** 4 frets comfortably (index–pinky stretch); 5 with a stretch.

### Candidate generation

For a given MIDI pitch p:
```
candidates = [
    (string_idx, fret)
    for string_idx, open_midi in enumerate(OPEN_STRINGS)
    if 0 <= (fret := p - open_midi) <= MAX_FRET
]
```

A middle C (MIDI 60) can be played on:
- String 5: fret 15 (A string)
- String 4: fret 10 (D string)
- String 3: fret 5 (G string)
- String 2: fret 1 (B string)
→ 4 candidates; the mapper chooses based on surrounding context.

---

## 4. Fretboard Mapping — Dynamic Programming

### State

At each time step t (quantized to 8th note grid), the *hand position* is the lowest
fret number currently in use (the position of the index finger). We model it as a
scalar `pos ∈ [0, MAX_FRET]`.

### Cost function

Given previous placement `(pos_prev)` and candidate `(string, fret)` for the current note:

```
cost(prev_pos, string, fret) =
    w_shift × |fret - prev_pos|          # hand position shift
  + w_stretch × max(0, fret - prev_pos - MAX_SPAN)  # unplayable stretch
  + w_openstring × (1 if fret == 0 else 0) × -1     # slight preference for open strings (natural sound)
  + w_highfret × max(0, fret - 12)       # mild penalty for high frets (tone gets thin)
```

Weights (tunable, defaults):
- `w_shift = 1.0`
- `w_stretch = 100.0` (hard penalize unplayable positions)
- `w_openstring = 0.5`
- `w_highfret = 0.2`

### Algorithm

1. For each note event, sorted by onset time:
   a. Generate all valid (string, fret) candidates.
   b. For each candidate, compute cost from each previous state.
   c. Keep the best previous state per candidate (Viterbi-style DP).
2. Backtrack through DP table to recover the full sequence.

Time complexity: O(N × C²) where N = number of notes, C = average candidates per note (~4).

### Polyphonic chords

Notes with overlapping time ranges form a *chord group*. Within a chord:
- All notes must be reachable from a single hand position.
- The combined stretch (max_fret - min_fret of the group) must be ≤ MAX_SPAN.
- If no valid voicing exists, prefer higher-string variants (drop the bass note
  to the next available position).

---

## 5. Source Separation

We use [Demucs](https://github.com/facebookresearch/demucs) `htdemucs_6s` (6-source model)
which separates: drums, bass, other, vocals, guitar, piano.

```bash
python -m demucs --two-stems=guitar input.mp3
```

The `guitar` stem is passed to AMT. Songs without prominent electric/acoustic guitar
will produce a noisy stem; we expose a `--no-sep` flag to skip separation.

---

## 6. Note Detection — BasicPitch

[BasicPitch](https://github.com/spotify/basic-pitch) is Spotify's open-source
neural AMT model. It:
- Runs on CPU without GPU in reasonable time (< 30s for a 3-min song)
- Handles polyphony well (up to ~6 simultaneous notes)
- Outputs onset/offset/pitch with per-note confidence
- Detects pitch bends (useful for future technique annotation)

```python
from basic_pitch.inference import predict

model_output, midi_data, note_events = predict(audio_path)
# note_events: list of (start_time_s, end_time_s, pitch_midi, amplitude, pitch_bends)
```

**Confidence threshold** (`min_note_length`, `minimum_frequency`, `onset_threshold`):
- Default onset_threshold = 0.5 works well for clean recordings.
- For noisy/mixed recordings, raise to 0.6–0.7 to reduce false positives.

---

## 7. Tab Rendering

### ASCII tab format (v1)

Standard 6-line ASCII tab, read left to right:

```
e|---0---3---5---|
B|---1---3---5---|
G|---0---2---5---|
D|---2---0---3---|
A|---2-------3---|
E|---0-------1---|
```

Each measure is `beat_width` characters wide. Notes within a beat share a column.

### Guitar Pro format (v2 — stretch goal)

Use the [guitarpro](https://github.com/slundi/guitarpro) Python library to write `.gp5`
files. This enables:
- Proper tempo and time signature
- Bend annotations
- Playback in Guitar Pro / TuxGuitar

---

## 8. Technique Detection (future work)

Post-process the note sequence to annotate common techniques:

| Technique | Detection heuristic |
|---|---|
| Hammer-on (h) | Two notes on same string, ascending pitch, overlapping time, no re-attack |
| Pull-off (p) | Two notes on same string, descending pitch, overlapping time, no re-attack |
| Slide (/ or \\) | Note followed by same-string note with pitch glide (from pitch bend data) |
| Bend (b) | Pitch bend data shows > 0.5 semitone upward glide on same note |
| Vibrato (~) | Pitch oscillation pattern within a sustained note |

---

## 9. Datasets

### GuitarSet (primary)
- 360 audio recordings with fully annotated tabs (string, fret, onset, offset)
- 6 guitarists × 5 musical genres × 6 patterns × 2 mic types
- Available at: https://guitarset.weebly.com/
- License: Creative Commons Attribution 4.0

### DadaGP
- 26,000+ Guitar Pro files scrapped from the web, converted to JSON
- Rich for training / fine-tuning fretboard assignment models
- Provides realistic tab sequences including technique annotations

### IDMT-SMT-Guitar
- Isolated guitar note recordings across pitch/technique/style variations
- Useful for training per-note technique classifiers

---

## 10. Evaluation Metrics

### AMT quality
- **Frame-level F1** (precision/recall of active pitches per time frame) — standard AMT metric
- **Note-level F1** (precision/recall of note onset ± 50ms, pitch match)

### Fretboard mapping quality
- **String accuracy**: % of notes assigned to the correct string (vs. GuitarSet ground truth)
- **Playability rate**: % of chord groups with valid hand span (≤ 4 frets)
- **Hand position jumps/bar**: lower is better; compare against human-authored tabs

### End-to-end
- Compare generated ASCII tab vs. verified human tabs (from GuitarSet) using
  string/fret accuracy, evaluated on held-out test set.

---

## 11. Development Roadmap

### Phase 1 — MVP (this session)
- [x] Design document
- [x] Core Python modules: `audio.py`, `detect.py`, `fretboard.py`, `tab.py`, `pipeline.py`
- [x] CLI: `tabpls transcribe input.mp3`
- [ ] Unit tests for fretboard mapper (edge cases)
- [ ] Integration test on one GuitarSet example

### Phase 2 — Accuracy
- [ ] Fine-tune BasicPitch on GuitarSet guitar-isolated audio
- [ ] Train learned fretboard mapper (replace DP cost weights with a small MLP)
- [ ] Technique detection (hammer-on / pull-off as first targets)
- [ ] Benchmark vs. TabCNN on GuitarSet test split

### Phase 3 — Product
- [ ] Web app (FastAPI + React or Next.js)
- [ ] GPU inference endpoint (Replicate.com or Modal.com)
- [ ] Guitar Pro (.gp5) export
- [ ] Chrome extension: "get tab for this YouTube video"

---

## 12. Dependencies

```
# Core pipeline
librosa>=0.10          # audio loading, CQT
numpy>=1.24
basic-pitch>=0.4       # AMT (Spotify)

# Source separation (optional)
demucs>=4.0

# Tab export (optional, phase 2)
guitarpro>=0.11

# Development
pytest
soundfile
```

Install:
```bash
pip install librosa numpy basic-pitch
# Optional:
pip install demucs guitarpro
```
