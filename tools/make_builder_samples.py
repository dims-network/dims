#!/usr/bin/env python3
"""Regenerate the example study that ships with the builder.

The builder's **Load the example study** button stages every file in
`apps/builder/samples/`. That folder holds ConvoConnect-Mini: three synthetic
dyads modelled on Case Study 1 of the DIMS paper -- stranger pairs in a
three-minute get-to-know-you conversation, with inter-brain synchrony, motion
tracking, a transcript and ELAN phase codes.

Everything here is generated, seeded and reproducible: the signals, the video
and the annotations come from one script so they agree with each other. A peak
in `rtpjsync` really is the moment the two partners laugh together, because the
same conversation script drives the numbers, the picture and the words.

    python tools/make_builder_samples.py           # write into apps/builder/samples
    python tools/make_builder_samples.py --check    # regenerate elsewhere and diff
    python tools/make_builder_samples.py --out DIR  # write somewhere else

Needs numpy, Pillow and ffmpeg (via imageio-ffmpeg, which the builder installs).

This script must NOT live inside `samples/`: the samples endpoint globs that
directory and stages everything in it that is not a `.md`, so a stray `.py`
would arrive in the wizard as an upload.
"""
from __future__ import annotations

import argparse
import filecmp
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(os.path.dirname(HERE), "apps", "builder", "samples")

FS_FAST = 25.0          # motion tracking, Hz
FS_SLOW = 5.0           # windowed synchrony measures, Hz
VIDEO_FPS = 12.5
VIDEO_W, VIDEO_H = 480, 270
EAF_DATE = "2026-01-15T09:00:00+01:00"   # fixed, so the output is byte-stable

L = "Left partner"
R = "Right partner"
PAUSE = None


# --------------------------------------------------------------------------
# The conversations
#
# (speaker, seconds, text) -- PAUSE for silence. Durations are what the video
# and the speaking-driven movement signals are built from, so they are the
# session's clock. Peaks name the moments the latent engagement process rises;
# they sit on turns where something actually happens between the two people.
# --------------------------------------------------------------------------

DYADS = {
    "dyad01": {
        "seed": 20260115,
        "coupling": 1.0,
        "video_extra": 0.0,
        "peaks": ["On the homepage.",
                  "Oh, that's exactly my story",
                  "the lighthouse!",
                  "This is a strange way to meet someone."],
        "phases": [
            (0.0, 25.5, "warm-up"),
            (25.5, 57.5, "topic: hometown"),
            (57.5, 107.5, "topic: work"),
            (107.5, 145.5, "shared laughter"),
            (145.5, 180.0, "closing"),
        ],
        "turns": [
            (L, 4.0, "Hi — I'm supposed to just start talking, right?"),
            (R, 3.5, "I think so. They said 'get to know each other'."),
            (L, 3.0, "Very specific."),
            (R, 3.5, "Extremely. Okay — where are you from?"),
            (L, 4.5, "Originally? A small town about two hours north of here."),
            (R, 3.0, "How small is small?"),
            (L, 4.0, "One bakery, one bus, and everyone knows the bus driver."),
            (R, 4.5, "That's smaller than mine, and mine had one traffic light."),
            (L, 3.5, "One traffic light is basically a city."),
            (R, 4.0, "We were extremely proud of that light."),
            (L, 4.0, "I bet there was a photo of it in the town hall."),
            (R, 3.5, "There was a photo of it on the town website."),
            (L, 3.0, "No."),
            (R, 3.0, "On the homepage."),
            (PAUSE, 2.0, None),
            (L, 4.5, "Okay, that is genuinely the best thing I've heard today."),
            (R, 4.0, "So what brought you down here, then?"),
            (L, 5.0, "Work, mostly. I moved for a job I thought was temporary."),
            (R, 3.0, "And?"),
            (L, 4.5, "That was six years ago."),
            (R, 4.5, "Oh, that's exactly my story. Two years, allegedly."),
            (L, 3.5, "How long has it actually been?"),
            (R, 3.0, "Nine."),
            (L, 3.5, "Nine!"),
            (R, 4.5, "I've stopped telling people it's temporary."),
            (L, 5.0, "I still say it. I don't think anyone believes me anymore."),
            (R, 4.0, "Do you believe you?"),
            (L, 3.5, "…No."),
            (PAUSE, 2.0, None),
            (R, 4.5, "What do you do when you're not being temporary?"),
            (L, 5.0, "Long walks and terrible films, mostly."),
            (R, 3.0, "Define terrible."),
            (L, 4.5, "The kind where the shark is clearly a balloon."),
            (R, 4.0, "Oh — I know the one you mean —"),
            (L, 3.0, "The one with the—"),
            (R, 2.5, "—the lighthouse!"),
            (L, 3.0, "The lighthouse!"),
            (R, 4.0, "That film is a masterpiece and I will not be corrected."),
            (L, 4.5, "I have never met anyone else who has seen it."),
            (R, 4.0, "Well. Now you have."),
            (PAUSE, 2.0, None),
            (L, 4.5, "This is a strange way to meet someone."),
            (R, 4.0, "It's working, though."),
            (L, 3.5, "It is, weirdly."),
            (R, 4.5, "Are they going to tell us when to stop?"),
            (L, 3.5, "I hope not immediately."),
            (R, 4.0, "Then we've got time. Terrible films — go."),
            (PAUSE, 4.5, None),
        ],
    },
    "dyad02": {
        "seed": 20260116,
        "coupling": 0.85,
        "video_extra": 0.0,
        "peaks": ["That's not sad, that's efficient.",
                  "A cheese sandwich.",
                  "The car has friends.",
                  "Lake. But I'd go to the coast with you."],
        "phases": [
            (0.0, 21.0, "warm-up"),
            (21.0, 58.0, "topic: food"),
            (58.0, 100.0, "topic: travel"),
            (100.0, 141.0, "shared laughter"),
            (141.0, 180.0, "closing"),
        ],
        "turns": [
            (R, 3.5, "Do we introduce ourselves, or is that cheating?"),
            (L, 3.5, "I think names are allowed."),
            (R, 3.0, "Good, because I'd forgotten mine."),
            (L, 4.0, "That's a very relaxing thing to hear from a stranger."),
            (R, 3.5, "I'm nervous. I talk about food when I'm nervous."),
            (L, 3.5, "That is an excellent thing to be nervous about."),
            (PAUSE, 3.0, None),
            (R, 4.5, "Okay: what did you have for breakfast? Be honest."),
            (L, 4.0, "Cold rice with an egg on it. Standing up."),
            (R, 3.5, "That's not sad, that's efficient."),
            (L, 3.5, "Thank you. My flatmate disagrees."),
            (R, 4.0, "Your flatmate is having toast, isn't she."),
            (L, 3.0, "Every single day."),
            (R, 4.0, "There's no imagination in toast."),
            (L, 4.5, "There's a little. There's what goes on the toast."),
            (R, 4.0, "Fine. There's a little."),
            (PAUSE, 2.5, None),
            (L, 4.5, "Where's the best thing you've ever eaten, then?"),
            (R, 5.0, "A bus station in northern Portugal, and I'm not joking."),
            (L, 3.0, "A bus station."),
            (R, 4.5, "The woman behind the counter did one thing perfectly."),
            (L, 3.5, "What was the thing?"),
            (R, 4.0, "A cheese sandwich. That's it. That's the story."),
            (L, 4.5, "I've been chasing a sandwich like that for years."),
            (R, 4.0, "You never find it again. That's the deal."),
            (L, 4.0, "Is that why you keep going back?"),
            (R, 4.5, "Honestly? Probably. I keep booking the same coast."),
            (L, 4.0, "I do the same with one lake. Every summer."),
            (R, 3.5, "Same week every year?"),
            (L, 3.0, "Same week. Same cabin."),
            (R, 3.5, "Do they know you by name?"),
            (L, 3.5, "They know me by car."),
            (PAUSE, 3.0, None),
            (R, 4.0, "That's worse. That's so much worse."),
            (L, 4.5, "They wave at the car before they see who's in it."),
            (R, 3.5, "The car has a relationship."),
            (L, 3.0, "The car has friends."),
            (R, 4.0, "You are simply the car's driver."),
            (L, 4.5, "I've never felt so accurately described."),
            (PAUSE, 2.0, None),
            (R, 4.5, "Okay, one more: lake week or the coast?"),
            (L, 3.5, "That's an unkind question."),
            (R, 3.0, "It's the only one left."),
            (L, 4.5, "Lake. But I'd go to the coast with you."),
            (R, 3.5, "That's the right answer."),
            (L, 3.0, "I know."),
            (R, 4.0, "We should have been given longer than this."),
            (PAUSE, 5.0, None),
        ],
    },
    "dyad03": {
        "seed": 20260117,
        "coupling": 0.18,
        "video_extra": 12.0,
        "peaks": ["I have one of those. You don't get a vote."],
        "phases": [
            (0.0, 32.0, "warm-up"),
            (32.0, 78.0, "topic: study"),
            (78.0, 120.0, "topic: weekend"),
            (120.0, 156.0, "topic shift"),
            (156.0, 180.0, "closing"),
        ],
        "turns": [
            (L, 3.5, "Hello."),
            (R, 2.5, "Hi."),
            (PAUSE, 3.0, None),
            (L, 4.0, "I think we're meant to talk until they say stop."),
            (R, 3.0, "Right. Yes."),
            (PAUSE, 3.0, None),
            (L, 3.5, "Have you done one of these before?"),
            (R, 3.0, "No. You?"),
            (L, 3.0, "No."),
            (PAUSE, 4.0, None),
            (R, 4.0, "It's warmer in here than I expected."),
            (L, 3.0, "It is, a bit."),
            (PAUSE, 3.0, None),
            (L, 4.5, "Are you a student here, or—"),
            (R, 4.0, "Yes. Second year. Chemistry."),
            (L, 3.0, "Oh, right."),
            (PAUSE, 3.0, None),
            (L, 3.5, "Is that going well?"),
            (R, 4.0, "It's fine. There's a lot of lab work."),
            (L, 3.0, "I imagine so."),
            (PAUSE, 3.5, None),
            (R, 3.5, "What about you?"),
            (L, 4.0, "Economics. Also fine."),
            (R, 2.5, "Right."),
            (PAUSE, 4.5, None),
            (L, 4.0, "Do you have plans for the weekend?"),
            (R, 4.5, "Not really. My sister's visiting, so probably that."),
            (L, 3.5, "Oh, that's nice."),
            (R, 3.0, "She's very loud."),
            (L, 3.5, "Loud in a good way?"),
            (R, 4.0, "Loud in a she-organises-everyone way."),
            (L, 4.5, "I have one of those. You don't get a vote."),
            (R, 4.0, "No. You get told the plan."),
            (L, 3.0, "Exactly."),
            (PAUSE, 3.5, None),
            (R, 3.5, "Anyway. It'll be fine."),
            (L, 2.5, "Yeah."),
            (PAUSE, 4.5, None),
            (L, 4.0, "Did they say how long this goes on for?"),
            (R, 3.0, "Three minutes, I think."),
            (L, 3.5, "That's longer than it sounds."),
            (R, 3.0, "It is."),
            (PAUSE, 4.0, None),
            (R, 3.5, "Do you know what the study's about?"),
            (L, 4.0, "Something about brains, they said."),
            (R, 3.0, "Helpful."),
            (PAUSE, 3.0, None),
            (L, 3.0, "Very."),
            (PAUSE, 3.5, None),
            (R, 3.5, "I think that might be it."),
            (L, 2.5, "I think so."),
            (PAUSE, 3.0, None),
        ],
    },
}


# --------------------------------------------------------------------------
# Signals
# --------------------------------------------------------------------------

def smooth(x, sigma_samples):
    """Gaussian smoothing, reflected at the ends.

    Not edge-padded: replicating one random end sample biases a long window
    hard enough to pin the first and last seconds of every signal at its
    saturation value.
    """
    sigma = max(float(sigma_samples), 1e-6)
    half = int(math.ceil(3 * sigma))
    k = np.exp(-0.5 * (np.arange(-half, half + 1) / sigma) ** 2)
    k /= k.sum()
    padded = np.pad(x, half, mode="reflect")
    return np.convolve(padded, k, mode="valid")


def unit(x):
    x = np.asarray(x, dtype=float)
    sd = x.std()
    return (x - x.mean()) / (sd if sd > 1e-12 else 1.0)


def lag_by(x, seconds, fs=FS_FAST):
    """Delay a signal, holding its first value over the gap it opens."""
    k = int(round(seconds * fs))
    if k <= 0:
        return x
    return np.concatenate([np.full(k, x[0]), x[:-k]])


def bumpy(rng, n, sigma_s, fs=FS_FAST):
    """A positive, uneven envelope — movement comes in bursts, not at a level."""
    return 0.35 + np.abs(unit(smooth(rng.standard_normal(n), sigma_s * fs)))


def segments_of(turns):
    """Turn the script into transcript segments and a clock."""
    out, t = [], 0.0
    for speaker, dur, text in turns:
        if speaker is not None:
            out.append({"start": round(t, 2), "end": round(t + dur, 2),
                        "speaker": speaker, "text": text})
        t += dur
    return out, t


def speaking_masks(segments, n, fs=FS_FAST):
    """1.0 while that partner holds the floor, 0.0 otherwise."""
    t = np.arange(n) / fs
    left = np.zeros(n)
    right = np.zeros(n)
    for s in segments:
        m = (t >= s["start"]) & (t < s["end"])
        (left if s["speaker"] == L else right)[m] = 1.0
    return left, right


def peak_times(spec):
    """When engagement rises, in seconds.

    A peak is named by the line it belongs to rather than by a number, so
    rewriting a turn moves the peak with it instead of quietly detaching the
    signal from the conversation it is supposed to explain.
    """
    out = []
    for want in spec["peaks"]:
        if isinstance(want, (int, float)):
            out.append(float(want))
            continue
        hits = [s for s in spec["segments"] if want in s["text"]]
        if len(hits) != 1:
            raise SystemExit(f"{spec['dyad']}: peak {want!r} matches {len(hits)} lines")
        out.append((hits[0]["start"] + hits[0]["end"]) / 2)
    return out


def build_signals(spec):
    """Every measure for one dyad, from one latent engagement process.

    The story the numbers tell has to be the story the transcript tells, or the
    tutorial teaches the wrong lesson. So: engagement rises at the scripted
    moments; inter-brain synchrony follows it; head synchrony follows it a
    second and a half later; hands move when their owner speaks; heads nod when
    their owner listens; in the silences everything falls to a fidget.
    """
    dur = spec["duration"]
    n = int(round(dur * FS_FAST))
    rng = np.random.default_rng(spec["seed"])
    t = np.arange(n) / FS_FAST

    drift = unit(smooth(rng.standard_normal(n), 8.0 * FS_FAST))
    bumps = np.zeros(n)
    for p in peak_times(spec):
        bumps += np.exp(-((t - p) ** 2) / (2 * 6.0 ** 2))
    E = unit(spec["coupling"] * 2.2 * bumps + 0.9 * drift)
    E01 = (E - E.min()) / max(float(np.ptp(E)), 1e-9)

    n1 = unit(smooth(rng.standard_normal(n), 3.0 * FS_FAST))
    n2 = unit(smooth(rng.standard_normal(n), 3.5 * FS_FAST))
    n3 = unit(smooth(rng.standard_normal(n), 5.0 * FS_FAST))

    rtpj = 0.75 * np.tanh(0.95 * E + 0.45 * n1) + 0.10
    head = 0.70 * np.tanh(0.85 * lag_by(E, 1.5) + 0.55 * n2) + 0.06
    body = 0.60 * np.tanh(0.55 * unit(smooth(E, 6.0 * FS_FAST)) + 0.70 * n3) + 0.04

    segs = spec["segments"]
    speak_l, speak_r = speaking_masks(segs, n)
    sl = smooth(speak_l, 0.45 * FS_FAST)
    sr = smooth(speak_r, 0.45 * FS_FAST)

    def speed(own, other, gesture_gain, nod_gain, carrier_hz, seed_off):
        r = np.random.default_rng(spec["seed"] + seed_off)
        fidget = 0.035 * bumpy(r, n, 1.5)
        env = (gesture_gain * own * (0.55 + 0.60 * E01) * bumpy(r, n, 0.45)
               + nod_gain * other * (0.35 + 0.85 * E01) * bumpy(r, n, 0.60))
        phase = r.uniform(0, 2 * math.pi)
        carrier = 0.62 + 0.38 * np.sin(2 * math.pi * carrier_hz * t + phase)
        v = np.clip((fidget + env) * carrier, 0.0, None)
        p95 = np.percentile(v, 95)
        return v * (0.85 / p95) if p95 > 1e-9 else v

    out = {
        "rtpjsync": (FS_SLOW, rtpj),
        "headsync": (FS_SLOW, head),
        "bodysync": (FS_SLOW, body),
        "leftheadspeed": (FS_FAST, speed(sl, sr, 0.20, 0.60, 2.1, 11)),
        "rightheadspeed": (FS_FAST, speed(sr, sl, 0.20, 0.60, 2.0, 12)),
        "lefthandspeed": (FS_FAST, speed(sl, sr, 0.80, 0.06, 1.3, 13)),
        "righthandspeed": (FS_FAST, speed(sr, sl, 0.80, 0.06, 1.2, 14)),
    }
    # The synchrony measures are windowed estimates: they come out of a
    # 30 s window stepped a fifth of a second, so 5 Hz is their real rate.
    step = int(round(FS_FAST / FS_SLOW))
    return {k: (fs, v[::step] if fs == FS_SLOW else v) for k, (fs, v) in out.items()}


# --------------------------------------------------------------------------
# Writers
# --------------------------------------------------------------------------

def write_csv(path, columns, fs):
    """One time column in seconds plus one or more measures, ascending."""
    n = len(columns[0][1])
    lines = [",".join(["Time"] + [c[0] for c in columns])]
    times = np.arange(n) / fs
    cols = [np.round(c[1], 5) for c in columns]
    for i in range(n):
        lines.append(",".join([f"{times[i]:.3f}"] + [f"{c[i]:.5f}" for c in cols]))
    with open(path, "w", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def write_transcript(path, segments):
    with open(path, "w", newline="\n") as fh:
        json.dump({"segments": segments}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def write_eaf(path, phases, dyad):
    """A minimal ELAN document with one `phases` tier.

    Time slots are milliseconds, as ELAN stores them; the dashboard converts.
    """
    slots, ann = [], []
    times = []
    for start, end, _ in phases:
        times.extend([start, end])
    uniq = sorted(set(times))
    ids = {v: f"ts{i}" for i, v in enumerate(uniq)}
    for v in uniq:
        slots.append(f'<TIME_SLOT TIME_SLOT_ID="{ids[v]}" TIME_VALUE="{int(round(v * 1000))}"/>')
    for i, (start, end, label) in enumerate(phases):
        ann.append(
            f'<ANNOTATION><ALIGNABLE_ANNOTATION ANNOTATION_ID="a{i}" '
            f'TIME_SLOT_REF1="{ids[start]}" TIME_SLOT_REF2="{ids[end]}">'
            f"<ANNOTATION_VALUE>{label}</ANNOTATION_VALUE>"
            "</ALIGNABLE_ANNOTATION></ANNOTATION>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<ANNOTATION_DOCUMENT AUTHOR="ConvoConnect-Mini (synthetic)" DATE="{EAF_DATE}" '
        'FORMAT="3.0" VERSION="3.0">'
        f'<HEADER MEDIA_FILE="" TIME_UNITS="milliseconds">'
        f'<MEDIA_DESCRIPTOR MEDIA_URL="./{dyad}.mp4" MIME_TYPE="video/mp4"/></HEADER>'
        f'<TIME_ORDER>{"".join(slots)}</TIME_ORDER>'
        f'<TIER LINGUISTIC_TYPE_REF="default" TIER_ID="phases">{"".join(ann)}</TIER>'
        '<LINGUISTIC_TYPE GRAPHIC_REFERENCES="false" LINGUISTIC_TYPE_ID="default" '
        'TIME_ALIGNABLE="true"/>'
        "</ANNOTATION_DOCUMENT>"
    )
    with open(path, "w", newline="\n") as fh:
        fh.write(xml + "\n")


# --------------------------------------------------------------------------
# Video
# --------------------------------------------------------------------------

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def load_font(size):
    from PIL import ImageFont
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:  # noqa: BLE001 — unusable face, try the next
                pass
    return ImageFont.load_default()


def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:2]


def render_video(path, spec, signals):
    """A stand-in for the recording, drawn from the signals themselves.

    Not a pretty picture for its own sake: the two figures move with the very
    traces the dashboard plots, so clicking a peak in the dashboard shows two
    people moving together, which is the whole gesture the tool exists for.
    """
    from PIL import Image, ImageDraw

    exe = ffmpeg_exe()
    duration = spec["duration"] + spec["video_extra"]
    n_frames = int(round(duration * VIDEO_FPS))
    cap_font, meta_font = load_font(15), load_font(12)

    def sample(name, t):
        fs, v = signals[name]
        i = min(int(round(t * fs)), len(v) - 1)
        return float(v[i])

    segs = spec["segments"]
    seg_idx = 0
    proc = subprocess.Popen(
        [exe, "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{VIDEO_W}x{VIDEO_H}", "-r", str(VIDEO_FPS), "-i", "-",
         "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "30",
         "-threads", "1", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         path],
        stdin=subprocess.PIPE,
    )

    WALL, TABLE = (232, 233, 236), (206, 200, 190)
    SKIN_L, SKIN_R = (58, 148, 152), (200, 138, 62)
    BAND = (26, 28, 33)
    cap_top = VIDEO_H - 46

    for f in range(n_frames):
        t = f / VIDEO_FPS
        img = Image.new("RGB", (VIDEO_W, VIDEO_H), WALL)
        d = ImageDraw.Draw(img)
        d.rectangle([0, VIDEO_H - 96, VIDEO_W, VIDEO_H], fill=TABLE)

        while seg_idx < len(segs) and t >= segs[seg_idx]["end"]:
            seg_idx += 1
        seg = segs[seg_idx] if seg_idx < len(segs) and t >= segs[seg_idx]["start"] else None

        for side in ("left", "right"):
            cx = 130 if side == "left" else VIDEO_W - 130
            colour = SKIN_L if side == "left" else SKIN_R
            hs = sample(f"{side}headspeed", t)
            gs = sample(f"{side}handspeed", t)
            speaking = seg is not None and seg["speaker"] == (L if side == "left" else R)

            nod = 9 * min(hs, 1.4) * math.sin(2 * math.pi * 2.1 * t + (0 if side == "left" else 1.1))
            head_y = 108 + nod
            d.rounded_rectangle([cx - 44, 150, cx + 44, VIDEO_H - 70], 16, fill=colour)
            d.ellipse([cx - 30, head_y - 30, cx + 30, head_y + 30], fill=colour)
            if speaking:
                d.ellipse([cx - 34, head_y - 34, cx + 34, head_y + 34], outline=(250, 250, 250), width=3)
                mouth = 3 + 4 * abs(math.sin(2 * math.pi * 3.4 * t))
                d.ellipse([cx - 8, head_y + 9 - mouth / 2, cx + 8, head_y + 9 + mouth / 2],
                          fill=(30, 30, 34))
            else:
                d.line([cx - 8, head_y + 10, cx + 8, head_y + 10], fill=(30, 30, 34), width=2)
            for eye in (-11, 11):
                d.ellipse([cx + eye - 3, head_y - 6, cx + eye + 3, head_y], fill=(30, 30, 34))

            r = 26 * min(gs, 1.4)
            ang = 2 * math.pi * 1.3 * t + (0.4 if side == "left" else 2.6)
            hx = cx + (34 if side == "left" else -34) + r * math.cos(ang)
            hy = 196 + r * math.sin(ang) * 0.7
            d.ellipse([hx - 11, hy - 11, hx + 11, hy + 11], fill=colour)

        d.rectangle([0, cap_top, VIDEO_W, VIDEO_H], fill=BAND)
        if seg is not None:
            who = "L" if seg["speaker"] == L else "R"
            lines = wrap(d, f"{who}: {seg['text']}", cap_font, VIDEO_W - 28)
            y = cap_top + (46 - 17 * len(lines)) / 2
            for line in lines:
                w = d.textlength(line, font=cap_font)
                d.text(((VIDEO_W - w) / 2, y), line, font=cap_font, fill=(244, 244, 246))
                y += 17

        clock = f"{int(t) // 60}:{int(t) % 60:02d} / {int(duration) // 60}:{int(duration) % 60:02d}"
        d.text((VIDEO_W - 14 - d.textlength(clock, font=meta_font), 10), clock,
               font=meta_font, fill=(120, 122, 128))
        d.text((14, 10), spec["dyad"], font=meta_font, fill=(120, 122, 128))

        proc.stdin.write(img.tobytes())

    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit(f"ffmpeg failed writing {path}")


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 — fall back to whatever is on PATH
        exe = shutil.which("ffmpeg")
        if not exe:
            raise SystemExit("No ffmpeg. `pip install imageio-ffmpeg`.")
        return exe


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

# How each dyad's time series are laid out on disk. `dyad02` ships its four
# motion measures in one wide CSV because that is what a motion-tracking export
# looks like — and it is what exercises the builder's auto-split on upload.
WIDE_CSV = {"dyad02": ["leftheadspeed", "rightheadspeed", "lefthandspeed", "righthandspeed"]}

SYNC = ("rtpjsync", "headsync", "bodysync")


def build_dyad(dyad, out_dir, quiet=False):
    cfg = DYADS[dyad]
    segments, duration = segments_of(cfg["turns"])
    spec = dict(cfg, dyad=dyad, segments=segments, duration=duration)
    signals = build_signals(spec)

    wide = WIDE_CSV.get(dyad, [])
    for name, (fs, values) in signals.items():
        if name in wide:
            continue
        write_csv(os.path.join(out_dir, f"{dyad}_{name}.csv"), [(name, values)], fs)
    if wide:
        write_csv(os.path.join(out_dir, f"{dyad}.csv"),
                  [(n, signals[n][1]) for n in wide], signals[wide[0]][0])

    write_transcript(os.path.join(out_dir, f"{dyad}_transcript.json"), segments)
    write_eaf(os.path.join(out_dir, f"{dyad}.eaf"), cfg["phases"], dyad)
    if not quiet:
        print(f"  {dyad}: signals, transcript, ELAN — rendering video…", flush=True)
    render_video(os.path.join(out_dir, f"{dyad}.mp4"), spec, signals)
    return spec


def generate(out_dir, quiet=False):
    os.makedirs(out_dir, exist_ok=True)
    for dyad in sorted(DYADS):
        build_dyad(dyad, out_dir, quiet=quiet)


def data_files(d):
    return sorted(n for n in os.listdir(d)
                  if not n.startswith(".") and not n.endswith(".md")
                  and os.path.isfile(os.path.join(d, n)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help="where to write (default: apps/builder/samples)")
    ap.add_argument("--check", action="store_true",
                    help="regenerate into a temp dir and diff against --out")
    args = ap.parse_args(argv)

    if args.check:
        with tempfile.TemporaryDirectory() as tmp:
            generate(tmp, quiet=True)
            here, there = data_files(args.out), data_files(tmp)
            if here != there:
                print("file list differs")
                print("  committed:", here)
                print("  generated:", there)
                return 1
            match, mismatch, errors = filecmp.cmpfiles(args.out, tmp, here, shallow=False)
            if mismatch or errors:
                print("content differs:", sorted(mismatch + errors))
                return 1
            print(f"{len(match)} files, all identical")
            return 0

    # Writing for real: the old sample sessions go, or the wizard would stage
    # both studies at once.
    if os.path.isdir(args.out):
        for name in data_files(args.out):
            if name.startswith("session"):
                os.remove(os.path.join(args.out, name))
    print(f"writing ConvoConnect-Mini into {args.out}")
    generate(args.out)
    total = sum(os.path.getsize(os.path.join(args.out, n)) for n in data_files(args.out))
    print(f"done — {len(data_files(args.out))} files, {total / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
