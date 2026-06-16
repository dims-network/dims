# Sample dataset — one session (`session1`)

Mock files for testing the builder end-to-end. All validate cleanly against the
builder's rules. They describe a single session whose ID is **`session1`**.

| File | Role | Notes |
|------|------|-------|
| `session1.mp4` | video | Real 10 s H.264 clip (plays in any browser, supports seeking) |
| `session1_bodysync.csv` | timeseries | `Time` + `value`, 0–10 s @ 50 Hz, data type `bodysync` |
| `session1_neuralsync.csv` | timeseries | same span, data type `neuralsync` (phase-coupled to bodysync) |
| `session1_transcript.json` | transcript | `{ segments: [{start,end,speaker,text}] }` |
| `session1.eaf` | ELAN | tier `phases` with a few annotations |

## How to test

1. From the builder root: `python builder.py` (browser opens to the wizard).
2. **Step 1** — pick an empty output folder; for an offline run choose
   "local template folder" and point it at your local
   `DIMS_dashboard_template`. Set a title.
3. **Step 2** — drag all five files in this folder into the dropzone (or use
   *browse*). The two CSVs come in as data types `bodysync` / `neuralsync`; the
   rest map to `session1` automatically.
4. **Step 3** — enable **RQA** (both types) and **cross-wavelet** (the pair); the
   signals are designed so both analyses produce visible structure. Optionally
   enable ELAN.
5. **Build → Precompute → Preview** — the dashboard opens with the video,
   time-series, RQA, and cross-wavelet tabs populated.

> These signals are synthetic (two phase-coupled sinusoids + noise), chosen so
> the analyses are non-trivial — not real recordings.
