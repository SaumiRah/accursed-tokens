# TabPls — Business Model & Go-to-Market

> Auto-transcription from audio to guitar tab. This is where guitarists are — not sheet music.

---

## The Market

**Target audience:** Guitar players who want to learn songs by ear.

- ~50 million guitarists in the US alone (NAMM, 2023)
- Guitar is the #1 instrument by total players globally
- The universal "how do I learn this song?" flow today: YouTube → Ultimate Guitar → hours of frustration
- Ultimate Guitar has **~40M monthly active users** and charges $6–$7/month for Pro. That's the benchmark.

**The gap:**
- Ultimate Guitar, Songsterr: human-authored tabs. Slow, inconsistent quality, incomplete catalog, locked behind subscription.
- Chordify: Detects chord changes, not individual fret positions. Good for rhythm guitar, useless for lead/riff learning.
- BasicPitch (Spotify): Free, outputs MIDI. No guitar-specific logic. Requires a DAW to use.
- No product does audio → guitar tab with fretboard intelligence, automatically, for any song.

**The opportunity:** Same TAM as Ultimate Guitar, but automated — so the catalog is theoretically unlimited. Any song, any time.

---

## Value Proposition

> "Hear a guitar riff you love. 30 seconds later, you have the tab."

That's the pitch. No waiting for a human tabber. No searching Songsterr. Just audio → playable guitar tab, instantly.

---

## Revenue Model

### Tier 1 — Free
- 5 transcriptions/month
- 3-minute max duration
- Standard tuning only
- ASCII tab output

### Tier 2 — Solo ($5/month)
- Unlimited transcriptions
- Full-length songs (up to 10 min)
- All tunings (drop D, open G, etc.)
- Download as ASCII tab, PDF, or Guitar Pro (.gp5)
- BPM detection (auto-set tempo for quantized rendering)

### Tier 3 — Band ($12/month)
- Everything in Solo
- Multi-instrument: bass tab, piano notes (BasicPitch handles polyphony)
- API access (100 calls/month) for developers
- Chord diagram overlay on tab
- MIDI export

### API (B2B)
- $0.05 per transcription (< 3 min), $0.12 per transcription (3–10 min)
- Volume discounts
- Target: music education apps, DAW plugin developers, music game studios

**Projected unit economics at 10k monthly subscribers:**
- Revenue: ~$60k ARR at $5/mo average
- GPU costs: ~$300/mo (Replicate.com, ~10s inference per song on T4)
- Gross margin: >95%

---

## Differentiation

| Feature | TabPls | Ultimate Guitar | Chordify |
|---|---|---|---|
| Automatic (any song) | ✓ | ✗ | ✓ |
| String/fret positions | ✓ | ✓ | ✗ (chords only) |
| Guitar Pro export | ✓ (v2) | ✓ | ✗ |
| Works on unreleased songs | ✓ | ✗ | ✓ |
| Price | $5/mo | $7/mo | $4/mo |

---

## Distribution

### Phase 1 — Organic (months 0–6)
- Launch on Product Hunt, Hacker News Show HN
- Reddit: r/guitar, r/learnguitar, r/WeAreTheMusicMakers
- TikTok/YouTube Shorts demo: upload a riff, get tab in real-time
- SEO: "guitar tab for [song name]" is a hugely searched query

### Phase 2 — Partnerships (months 6–18)
- Embed in guitar learning apps: Yousician, Fender Play, JustinGuitar
- License the API to DAW plugins (GarageBand, Logic Pro extensions)
- Collaborate with music YouTube channels (Paul Davids, Jared Dines) for demo content

### Phase 3 — Platform (months 18+)
- Community tab verification: AI generates, human guitarist rates/corrects
- Crowdsourced corrections improve model over time (flywheel)
- "Tab Store": sell AI-generated tabs for popular songs (same model as Shutterstock)

---

## Technical Risk & Mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| Accuracy not good enough for complex solos | Medium | Phase 1: focus on simpler songs; ship the 80% use case |
| Legal: copyright for tabs | Medium | Tabs are typically covered by "fair use" + user uploads; add DMCA compliance from day 1 |
| Demucs quality poor on some mixes | Low-medium | Expose `--no-sep` flag; let users upload isolated guitar audio |
| BasicPitch detects wrong notes | Medium | Tune threshold per genre; let users adjust sensitivity in UI |
| GPU inference costs spike | Low | Rate limit free tier; use Replicate.com serverless (pay per use) |

---

## Copyright / Legal Notes

- Guitar tabs exist in a legal gray area: copyright holders rarely pursue individual tabbers,
  but services have been sent takedown notices (GuitarWorld 2021, Songbook era).
- **Mitigation**: Don't host pre-generated tabs in a searchable database. Generate on demand,
  don't cache or index. DMCA safe harbor applies when acting on takedown notices promptly.
- Alternative: License a small catalog from publishers initially (Hal Leonard, Alfred Music)
  to build credibility, then use AI for the long tail.
- EU and Australian copyright law differ from US; consult a music industry attorney before
  expanding to EU.

---

## Stack (production)

```
Frontend:    Next.js + Tailwind CSS
Backend API: FastAPI (Python)
Inference:   Modal.com (serverless GPU) or Replicate.com
Storage:     S3 for audio uploads, PostgreSQL for user data
Auth:        Clerk or Supabase
Payments:    Stripe
```

Estimated cold-start deployment time: 2–3 months for a solo developer with existing ML code.

---

## Milestones

| Milestone | Target date | Success metric |
|---|---|---|
| MVP working on GuitarSet test set | Month 1 | >60% note F1, >70% string accuracy |
| Public beta (free tier) | Month 2 | 500 sign-ups, 100 active users |
| Paid tier launch | Month 3 | 50 paying users |
| $1k MRR | Month 4 | ~200 Solo subscribers |
| $10k MRR | Month 9 | Requires either 2k Solo or 800 Band subscribers |

---

## Why Now

- BasicPitch (2022) made accurate polyphonic guitar AMT finally practical without custom training.
- Demucs v4 (2023) made guitar isolation from mixes good enough for real songs.
- Modal.com / Replicate.com made GPU inference serverless, eliminating infra setup cost.
- The tab-as-a-service market is largely untouched — Ultimate Guitar is the only real incumbent
  and they're focused on their existing human-authored catalog, not automation.
