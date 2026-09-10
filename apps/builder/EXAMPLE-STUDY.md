# ConvoConnect-Mini — the example study

Press **Load the example study** in step 2 of the wizard and this is what
arrives. Two dyads, three minutes each, everything synthetic.

It is modelled on Case Study 1 of the DIMS paper: stranger pairs holding a
get-to-know-you conversation while portable fNIRS records both brains, with the
video, the transcript and the motion tracking kept on one clock. The point of
that case study is that a rise in inter-brain synchrony is not the finding but
the question — you go back to the conversation to find out what kind of moment
it was. These files exist so you can try exactly that before you have data of
your own.

> **Nothing ships and nothing is committed.** The study is generated on first
> use by [`dims_builder/example_study.py`](dims_builder/example_study.py) and
> cached, so it costs a few seconds once and no repository space ever. It needs
> nothing that is not already installed. To look at the files:
> `python tools/make_builder_samples.py --out ./example-study` from the
> repository root; `--check` generates twice and proves the two runs are
> byte-identical.

## The two dyads

| | what happens | why it is here |
|---|---|---|
| **dyad01** | Two people who click almost immediately: small towns, a job that was meant to be temporary, a film they both love. | The coupled case. Four synchrony peaks, each on a moment you can name. |
| **dyad02** | A conversation that never gets going: short answers, long silences, one exchange near the end where they briefly connect. | The uncoupled case: `rtpjSync` sits near zero and its largest peaks land on nothing. Its video also runs **12 s longer than its signals**, so step 3 has a real misalignment to fix. |

## What every study is made of

Four things, all on one clock. Each dyad has all four, and they are what the
tutorial's basic path uses:

| | |
|---|---|
| **A video** | `dyad01.mp4` — one per session |
| **Measurements** | five CSVs, each a `Time` column in seconds plus one measure |
| **A transcript** | `dyad01_transcript.json`, optional but the reason peaks mean anything |
| **ELAN codes** | `dyad01.eaf`, optional — one `phases` tier per conversation |

## The five measurements

Two hands each, and one belonging to the pair rather than to either partner.

| dataType | what it is | unit | rate |
|---|---|---|---|
| `personLeftLeftHandSpeed` | left-seat partner: **left** hand speed | normalised px/s, ≥ 0 | 12.5 Hz |
| `personLeftRightHandSpeed` | left-seat partner: **right** hand speed | normalised px/s, ≥ 0 | 12.5 Hz |
| `personRightLeftHandSpeed` | right-seat partner: left hand speed | normalised px/s, ≥ 0 | 12.5 Hz |
| `personRightRightHandSpeed` | right-seat partner: right hand speed | normalised px/s, ≥ 0 | 12.5 Hz |
| `rtpjSync` | the pair's inter-brain synchrony over right temporoparietal junction | r, −1…1 | 5 Hz |

**Which the optional analyses reach for.** Anything comparing two signals —
cross-recurrence, cross-wavelet, the network — wants the hands, because people
take turns and so do their hands. Anything looking at one signal wants
`rtpjSync`, which is where this study's story lives.

The hands are at 12.5 Hz because that is the video frame rate: tracking gives one
sample per frame. `rtpjSync` is one number for the two of them and comes from a
slower pipeline, so it has its own clock.

**These are mock signals.** Not a simulation of fNIRS or of motion tracking: they
are shaped so that what the dashboard draws lines up with what the transcript
says, which is the one property a tutorial dataset needs. Hands move when their
owner is speaking, at roughly fifty times the resting rate, and `rtpjSync` rises
at the moments the conversation turns.

The hand speeds are non-negative and fall to a fidget in the silences, so a flat
stretch on the plot reads as *this person went still* rather than as a signal
crossing zero on its way somewhere.

## The files

One folder per dyad, which is how the data sits on the disk it came from. The
wizard walks the tree, so one press picks up both.

```
dyad01/  dyad01.mp4   dyad01_personLeftLeftHandSpeed.csv    dyad01_rtpjSync.csv
         dyad01.eaf   dyad01_personLeftRightHandSpeed.csv
         dyad01_transcript.json
                      dyad01_personRightLeftHandSpeed.csv
                      dyad01_personRightRightHandSpeed.csv

dyad02/  the same five measures — video 192 s against 180 s of signal
```

Transcripts are `{ "segments": [{start, end, speaker, text}] }` with speakers
`Left partner` and `Right partner`. Each `.eaf` carries one `phases` tier —
`warm-up`, `topic: …`, `shared laughter`, `closing` — over the same clock.

The video is a stand-in drawn from the signals: each figure's two hands move
with that partner's two hand traces, and whoever is speaking is ringed. Nothing
on screen moves for a reason the data does not carry. There is no burned-in
subtitle, because the transcript sits beside the video in the dashboard and text
would have meant an image library this package does not need.

## Moments worth clicking

The whole argument in one gesture: find the peak, click it, read what was said.

**dyad01** — `rtpjSync` sits around +0.21, and its four highest points are
exactly the four moments the conversation turns:

| time | `rtpjSync` | what is happening |
|---|---|---|
| 0:49 | +0.89 | a joke lands — the town's traffic light was on the homepage |
| 1:16 | +0.90 | both moved here for a job that was supposed to be temporary |
| 2:12 | +0.87 | they finish each other's sentence about a film |
| 2:33 | +0.86 | "This is a strange way to meet someone." |

**dyad02** — sits at 0.00, and this is the one to spend time on. Its one real
moment is at 1:50 (+0.70), where they finally recognise something in each
other. Now look at where the signal is actually *highest*:

| time | `rtpjSync` | what is happening |
|---|---|---|
| 2:23 | +0.88 | "That's longer than it sounds." |
| 1:58 | +0.84 | "Exactly." |
| 1:13 | +0.81 | "What about you?" |

Nothing. In a pair who are not coupled, the biggest peaks are on nothing at
all — and they are bigger than the one moment that meant something. Reading a
peak without going back to the recording is how that gets published.

## Trying the analyses

Keep it small the first time. The four hand traces are the interesting ones for
a cross-analysis — they take turns, because people take turns — and two pairs is
plenty:

- `personLeftLeftHandSpeed × personRightLeftHandSpeed`
- `personLeftRightHandSpeed × personRightRightHandSpeed`

Those two are also the whole cross-effector network: four hands, two people, two
lines between them. `rtpjSync` belongs to the pair rather than to a body, so it
has nowhere to sit on a figure — leave it off the diagram and read it in the
time-series tab, which is where it does its work.

### What those two pairs come out as

Measured on this study, as the share of tested cells beating the 95 % chance
level — above 15 % the network draws a solid edge, below it a dashed one:

| pair | dyad01 | dyad02 |
|---|---|---|
| left hand × left hand | 28 % · solid | 27 % · solid |
| right hand × right hand | 28 % · solid | **12 % · dashed** |

**The network does not sort the two dyads for you, and it should not.** People
take turns whether or not the conversation is going anywhere, and their hands
take turns with them — which is why the left-hand edge is solid in both. The
difference between these two pairs lives in `rtpjSync`, where dyad01 peaks four
times on moments you can name and dyad02 sits at zero.

That is worth sitting with before you read your own network. An edge tells you
that two measures moved together, and coordination is not rapport.

**Cross-wavelet on its own is quick. The network is what costs.** Switching the
network on switches on the coherence chance level at 100 surrogates, because
without it no edge can be told from coincidence — and that simulation is the
slow part of the whole pipeline, run once per pair per session. Ask for ten
pairs instead of two and you have multiplied it by five.

Measured on these two dyads with those two pairs: **8–9½ minutes** at 100
surrogates (8:31 and 9:29 on two runs), **1 min 42 s** at 20. So for a first look you can drop the count to
20 in the cross-wavelet settings — but put it back before you read anything into
an edge, because the solid-or-dashed verdict is only as good as the null behind
it.

The null is cached in `~/.cache/dims/wct_significance`, keyed on what actually
changes it, so running the same pairs a second time is nearly instant. A fast
run is not evidence that the analysis was cheap.

