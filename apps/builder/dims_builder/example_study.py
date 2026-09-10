"""ConvoConnect-Mini — the example study, generated rather than shipped.

Pressing **Load the example study** in the wizard lands here. Two synthetic
dyads, three minutes each: a conversation, both partners' brains and hands and
heads, a transcript, ELAN phase codes and a stand-in video, all on one clock.

It is modelled on Case Study 1 of the DIMS paper — stranger pairs holding a
get-to-know-you conversation while portable fNIRS records both of them. The
point of that case study is that a rise in inter-brain synchrony is not the
finding but the question: you go back to the conversation to see what kind of
moment it was. These files exist so someone can try exactly that before they
have data of their own.

Nothing is committed to the repository. The whole study is generated on first
use and cached, which costs a few seconds once and no repository space ever.
It needs nothing that is not already installed: numpy is a core dependency and
the ffmpeg that encodes the video is the one `imageio-ffmpeg` provides for
trimming. The video frames are painted as numpy arrays for the same reason --
drawing them with an image library would mean adding one.

Everything is seeded, so the same input produces the same bytes.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile

import numpy as np

BUMP_SIGMA = 3.0        # width of a scripted moment, seconds

FS_MOTION = 12.5        # motion tracking: one sample per video frame
FS_SYNC = 5.0           # the pair's windowed measure, on its own slower clock
VIDEO_FPS = 12.5
VIDEO_W, VIDEO_H = 480, 270
EAF_DATE = "2026-01-15T09:00:00+01:00"   # fixed, so the output is byte-stable

L = "Left partner"
R = "Right partner"
PAUSE = None

# The five measures every dyad carries: two hands each, and one measure of the
# pair. No underscores in any name -- the wizard splits an uploaded filename on
# its last one to find the session id.
PEOPLE = ("personLeft", "personRight")
PER_PERSON = ("LeftHandSpeed", "RightHandSpeed")
SHARED = ("rtpjSync",)


# --------------------------------------------------------------------------
# The conversations
#
# (speaker, seconds, text) -- PAUSE for silence. Durations are what the video
# and the speaking-driven movement are built from, so they are the session's
# clock. Peaks name the moments engagement rises; each is named by the line it
# belongs to rather than by a number, so rewriting a turn moves the peak with
# it instead of quietly detaching the signal from the conversation.
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
        # Chosen so the one moment these two connect survives the private noise
        # around it: at every other point the measures go their own way.
        "seed": 20260125,
        "coupling": 0.25,
        # Weakly coupled throughout, so its one warm exchange has to be loud in
        # the shared process to survive the private noise around it.
        "bump_gain": 6.0,
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
    return np.convolve(np.pad(x, half, mode="reflect"), k, mode="valid")


def unit(x):
    x = np.asarray(x, dtype=float)
    sd = x.std()
    return (x - x.mean()) / (sd if sd > 1e-12 else 1.0)


def lag_by(x, seconds, fs):
    """Delay a signal, holding its first value over the gap it opens."""
    k = int(round(seconds * fs))
    return x if k <= 0 else np.concatenate([np.full(k, x[0]), x[:-k]])


def bumpy(rng, n, sigma_s, fs):
    """A positive, uneven envelope — movement comes in bursts, not at a level."""
    return 0.35 + np.abs(unit(smooth(rng.standard_normal(n), sigma_s * fs)))



def peak_times(spec):
    """When engagement rises, in seconds — resolved from the lines it names."""
    out = []
    for want in spec["peaks"]:
        if isinstance(want, (int, float)):
            out.append(float(want))
            continue
        hits = [s for s in spec["segments"] if want in s["text"]]
        if len(hits) != 1:
            raise ValueError(f"{spec['dyad']}: peak {want!r} matches {len(hits)} lines")
        out.append((hits[0]["start"] + hits[0]["end"]) / 2)
    return out


def segments_of(turns):
    """Turn the script into transcript segments and a clock."""
    out, t = [], 0.0
    for speaker, dur, text in turns:
        if speaker is not None:
            out.append({"start": round(t, 2), "end": round(t + dur, 2),
                        "speaker": speaker, "text": text})
        t += dur
    return out, t


def speaking_masks(segments, n, fs):
    """1.0 while that partner holds the floor, 0.0 otherwise."""
    t = np.arange(n) / fs
    left, right = np.zeros(n), np.zeros(n)
    for s in segments:
        m = (t >= s["start"]) & (t < s["end"])
        (left if s["speaker"] == L else right)[m] = 1.0
    return left, right


def build_signals(spec):
    """Every measure for one dyad, from one latent engagement process.

    The story the numbers tell has to be the story the transcript tells, or the
    example teaches the wrong lesson. So: engagement rises at the scripted
    moments, the pair's inter-brain synchrony rises with it, hands move when
    their owner is speaking, and in the silences everything falls back to a
    fidget.

    These are mock signals, not a simulation of fNIRS or of motion tracking.
    They are shaped so that what the dashboard draws lines up with what the
    transcript says, which is the one property a tutorial dataset needs.
    """
    dur = spec["duration"]
    n = int(round(dur * FS_MOTION)) + 1       # inclusive of t = dur
    n_sync = int(round(dur * FS_SYNC)) + 1
    rng = np.random.default_rng(spec["seed"])
    t = np.arange(n) / FS_MOTION

    drift = unit(smooth(rng.standard_normal(n), 8.0 * FS_MOTION))
    bumps = np.zeros(n)
    for p in peak_times(spec):
        bumps += np.exp(-((t - p) ** 2) / (2 * BUMP_SIGMA ** 2))
    shared = unit(spec.get("bump_gain", 2.8) * bumps + 0.9 * drift)

    # `coupling` is how much of the dyad's shared process reaches each partner;
    # what does not reach them is replaced by private noise. Engagement is per
    # person, not per dyad, because that is the difference between a coupled
    # pair and an uncoupled one: in dyad01 the two are nearly the same process,
    # in dyad02 they are mostly two people having separate experiences.
    c = float(spec["coupling"])

    def engagement(seed_off):
        r = np.random.default_rng(spec["seed"] + seed_off)
        own = unit(smooth(r.standard_normal(n), 4.0 * FS_MOTION))
        e = unit(c * shared + (1.0 - c) * own)
        return (e - e.min()) / max(float(np.ptp(e)), 1e-9)

    E01_l = engagement(101)
    E01_r = engagement(102)

    segs = spec["segments"]
    speak_l, speak_r = speaking_masks(segs, n, FS_MOTION)
    sl = smooth(speak_l, 0.45 * FS_MOTION)
    sr = smooth(speak_r, 0.45 * FS_MOTION)

    def hand(own, E01, carrier_hz, seed_off):
        """A hand: still, then gesturing while its owner talks."""
        r = np.random.default_rng(spec["seed"] + seed_off)
        fidget = 0.035 * bumpy(r, n, 1.5, FS_MOTION)
        gesture = 0.80 * own * (0.55 + 0.60 * E01) * bumpy(r, n, 0.45, FS_MOTION)
        carrier = 0.62 + 0.38 * np.sin(2 * math.pi * carrier_hz * t
                                       + r.uniform(0, 2 * math.pi))
        v = np.clip((fidget + gesture) * carrier, 0.0, None)
        p95 = np.percentile(v, 95)
        return v * (0.85 / p95) if p95 > 1e-9 else v

    # The pair's measure, on its own slower clock. It is one number for the two
    # of them, so it is drawn straight from the shared process rather than from
    # anything either partner carries alone: high where the scripted moments
    # are, wandering the rest of the time, and wandering nearly all of the time
    # in a pair that never connects.
    t_sync = np.arange(n_sync) / FS_SYNC
    r_sync = np.random.default_rng(spec["seed"] + 31)
    moments = np.interp(t_sync, t, bumps / max(float(bumps.max()), 1e-9))
    wander = unit(smooth(r_sync.standard_normal(n_sync), 6.0 * FS_SYNC))
    rtpj = np.tanh(1.9 * c * moments + (0.45 + 0.7 * (1.0 - c)) * wander) * 0.92

    return {
        "personLeftLeftHandSpeed": (FS_MOTION, hand(sl, E01_l, 1.3, 13)),
        "personLeftRightHandSpeed": (FS_MOTION, hand(sl, E01_l, 1.15, 14)),
        "personRightLeftHandSpeed": (FS_MOTION, hand(sr, E01_r, 1.2, 15)),
        "personRightRightHandSpeed": (FS_MOTION, hand(sr, E01_r, 1.35, 16)),
        "rtpjSync": (FS_SYNC, rtpj),
    }


# --------------------------------------------------------------------------
# Writers
# --------------------------------------------------------------------------

def write_csv(path, name, values, fs):
    """One time column in seconds plus one measure, ascending."""
    times = np.arange(len(values)) / fs
    rows = [f"{times[i]:.3f},{values[i]:.5f}" for i in range(len(values))]
    with open(path, "w", newline="\n") as fh:
        fh.write(f"Time,{name}\n" + "\n".join(rows) + "\n")


def write_transcript(path, segments):
    with open(path, "w", newline="\n") as fh:
        json.dump({"segments": segments}, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def write_eaf(path, phases, dyad):
    """A minimal ELAN document with one `phases` tier, in milliseconds."""
    uniq = sorted({v for start, end, _ in phases for v in (start, end)})
    ids = {v: f"ts{i}" for i, v in enumerate(uniq)}
    slots = "".join(f'<TIME_SLOT TIME_SLOT_ID="{ids[v]}" TIME_VALUE="{int(round(v * 1000))}"/>'
                    for v in uniq)
    ann = "".join(
        f'<ANNOTATION><ALIGNABLE_ANNOTATION ANNOTATION_ID="a{i}" '
        f'TIME_SLOT_REF1="{ids[start]}" TIME_SLOT_REF2="{ids[end]}">'
        f"<ANNOTATION_VALUE>{label}</ANNOTATION_VALUE></ALIGNABLE_ANNOTATION></ANNOTATION>"
        for i, (start, end, label) in enumerate(phases))
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<ANNOTATION_DOCUMENT AUTHOR="ConvoConnect-Mini (synthetic)" DATE="{EAF_DATE}" '
        'FORMAT="3.0" VERSION="3.0">'
        '<HEADER MEDIA_FILE="" TIME_UNITS="milliseconds">'
        f'<MEDIA_DESCRIPTOR MEDIA_URL="./{dyad}.mp4" MIME_TYPE="video/mp4"/></HEADER>'
        f"<TIME_ORDER>{slots}</TIME_ORDER>"
        f'<TIER LINGUISTIC_TYPE_REF="default" TIER_ID="phases">{ann}</TIER>'
        '<LINGUISTIC_TYPE GRAPHIC_REFERENCES="false" LINGUISTIC_TYPE_ID="default" '
        'TIME_ALIGNABLE="true"/></ANNOTATION_DOCUMENT>'
    )
    with open(path, "w", newline="\n") as fh:
        fh.write(xml + "\n")


# --------------------------------------------------------------------------
# Video — painted as numpy arrays, encoded by the ffmpeg that ships anyway
# --------------------------------------------------------------------------

# A 5x7 bitmap for the clock. Drawing text is the only thing in here that would
# have needed an image library, and a timecode is eleven glyphs.
GLYPHS = {
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    ":": ("00000", "00100", "00100", "00000", "00100", "00100", "00000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    " ": ("00000",) * 7,
}


def draw_text(img, x, y, text, colour, scale=2):
    for ch in text:
        rows = GLYPHS.get(ch, GLYPHS[" "])
        for ry, row in enumerate(rows):
            for rx, bit in enumerate(row):
                if bit == "1":
                    y0, x0 = y + ry * scale, x + rx * scale
                    img[y0:y0 + scale, x0:x0 + scale] = colour
        x += 6 * scale


def text_width(text, scale=2):
    return len(text) * 6 * scale


def fill_rect(img, x0, y0, x1, y1, colour):
    h, w = img.shape[:2]
    x0, x1 = max(0, int(x0)), min(w, int(x1))
    y0, y1 = max(0, int(y0)), min(h, int(y1))
    if x1 > x0 and y1 > y0:
        img[y0:y1, x0:x1] = colour


def fill_disc(img, cx, cy, r, colour, squash=1.0):
    """One filled ellipse, touching only its own bounding box."""
    h, w = img.shape[:2]
    ry = r * squash
    x0, x1 = max(0, int(cx - r) - 1), min(w, int(cx + r) + 2)
    y0, y1 = max(0, int(cy - ry) - 1), min(h, int(cy + ry) + 2)
    if x1 <= x0 or y1 <= y0:
        return
    yy = np.arange(y0, y1)[:, None]
    xx = np.arange(x0, x1)[None, :]
    mask = ((xx - cx) / r) ** 2 + ((yy - cy) / max(ry, 1e-6)) ** 2 <= 1.0
    img[y0:y1, x0:x1][mask] = colour


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 — fall back to whatever is on PATH
        exe = shutil.which("ffmpeg")
        if not exe:
            raise RuntimeError("No ffmpeg available; pip install imageio-ffmpeg")
        return exe


WALL = np.array([232, 233, 236], np.uint8)
TABLE = np.array([206, 200, 190], np.uint8)
INK = np.array([30, 30, 34], np.uint8)
DIM = np.array([150, 152, 158], np.uint8)
HILITE = np.array([250, 250, 250], np.uint8)
BODY = {"personLeft": np.array([58, 148, 152], np.uint8),
        "personRight": np.array([200, 138, 62], np.uint8)}


def render_video(path, spec, signals):
    """A stand-in for the recording, drawn from the signals themselves.

    Not decoration: the hands move with the very traces the dashboard plots and
    the speaker is ringed, so clicking a moment in the dashboard shows what was
    happening when it was measured. Nothing on screen moves for a reason the
    data does not carry. There is no burned-in subtitle — the transcript sits
    beside the video in the dashboard, and text here would mean an image
    library this package does not need.
    """
    duration = spec["duration"] + spec["video_extra"]
    n_frames = int(round(duration * VIDEO_FPS))

    def at(name, time):
        fs, v = signals[name]
        return float(v[min(int(round(time * fs)), len(v) - 1)])

    background = np.empty((VIDEO_H, VIDEO_W, 3), np.uint8)
    background[:] = WALL
    background[VIDEO_H - 96:] = TABLE

    segs = spec["segments"]
    seg_idx = 0
    clock_total = f"{int(duration) // 60}:{int(duration) % 60:02d}"

    proc = subprocess.Popen(
        [ffmpeg_exe(), "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{VIDEO_W}x{VIDEO_H}", "-r", str(VIDEO_FPS), "-i", "-",
         "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "30",
         "-threads", "1", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         path],
        stdin=subprocess.PIPE,
    )
    try:
        for f in range(n_frames):
            t = f / VIDEO_FPS
            img = background.copy()

            while seg_idx < len(segs) and t >= segs[seg_idx]["end"]:
                seg_idx += 1
            seg = (segs[seg_idx] if seg_idx < len(segs)
                   and t >= segs[seg_idx]["start"] else None)

            for person in PEOPLE:
                left_seat = person == "personLeft"
                cx = 130 if left_seat else VIDEO_W - 130
                colour = BODY[person]
                hand_colour = (colour.astype(int) + (255 - colour.astype(int)) * 0.42)
                hand_colour = hand_colour.astype(np.uint8)
                speaking = seg is not None and seg["speaker"] == (L if left_seat else R)

                # The head is fixed: nothing in this study measures it, and a
                # figure moving in a way no trace accounts for is the one thing
                # this picture must not do.
                head_y = 108
                fill_rect(img, cx - 44, 150, cx + 44, VIDEO_H - 70, colour)
                if speaking:
                    fill_disc(img, cx, head_y, 34, HILITE)
                fill_disc(img, cx, head_y, 30, colour)
                for eye in (-11, 11):
                    fill_disc(img, cx + eye, head_y - 3, 3.5, INK)
                if speaking:
                    mouth = 2.0 + 3.0 * abs(math.sin(2 * math.pi * 3.4 * t))
                    fill_disc(img, cx, head_y + 10, 8, INK, squash=mouth / 8)
                else:
                    fill_rect(img, cx - 8, head_y + 9, cx + 8, head_y + 11, INK)

                # The person's own left hand is on the viewer's right.
                for side, offset in (("LeftHand", 1), ("RightHand", -1)):
                    gs = at(person + side + "Speed", t)
                    r = 26 * min(gs, 1.4)
                    ang = 2 * math.pi * 1.3 * t + (0.4 if side == "LeftHand" else 2.6)
                    hx = cx + offset * 38 + r * math.cos(ang)
                    hy = 180 + r * math.sin(ang) * 0.7
                    fill_disc(img, hx, hy, 12, hand_colour)

            # Progress bar and clock, so a still frame says where it is.
            fill_rect(img, 0, VIDEO_H - 4, VIDEO_W, VIDEO_H, DIM)
            fill_rect(img, 0, VIDEO_H - 4, VIDEO_W * (f + 1) / n_frames, VIDEO_H, INK)
            clock = f"{int(t) // 60}:{int(t) % 60:02d} / {clock_total}"
            draw_text(img, VIDEO_W - 14 - text_width(clock), 12, clock, DIM)

            proc.stdin.write(img.tobytes())
    finally:
        proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed writing {path}")


# --------------------------------------------------------------------------
# Generating, and the cache that means it happens once
# --------------------------------------------------------------------------

def build_dyad(dyad, out_root):
    """Write one dyad into its own folder — that is how the data sits on the
    disk it came from, and the wizard walks the tree to find it."""
    out_dir = os.path.join(out_root, dyad)
    os.makedirs(out_dir, exist_ok=True)
    cfg = DYADS[dyad]
    segments, duration = segments_of(cfg["turns"])
    spec = dict(cfg, dyad=dyad, segments=segments, duration=duration)
    signals = build_signals(spec)

    for name, (fs, values) in signals.items():
        write_csv(os.path.join(out_dir, f"{dyad}_{name}.csv"), name, values, fs)
    write_transcript(os.path.join(out_dir, f"{dyad}_transcript.json"), segments)
    write_eaf(os.path.join(out_dir, f"{dyad}.eaf"), cfg["phases"], dyad)
    render_video(os.path.join(out_dir, f"{dyad}.mp4"), spec, signals)
    return spec


def generate(out_dir):
    """Write the whole example study into `out_dir`."""
    os.makedirs(out_dir, exist_ok=True)
    for dyad in sorted(DYADS):
        build_dyad(dyad, out_dir)
    return out_dir


def data_files(d):
    """Every generated file, as paths relative to `d`, in a stable order."""
    out = []
    for root, dirs, files in os.walk(d):
        dirs.sort()
        for name in sorted(files):
            if name.startswith("."):
                continue
            out.append(os.path.relpath(os.path.join(root, name), d))
    return sorted(out)


def fingerprint():
    """A short hash of this module, so changing the generator invalidates the
    cache rather than serving a study that no longer matches the code."""
    with open(os.path.abspath(__file__), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:12]


def cache_root():
    """Where a generated study is kept between runs.

    A user cache directory when there is one, the temp directory otherwise --
    never inside the package, which may be installed read-only.
    """
    base = os.environ.get("DIMS_BUILDER_CACHE")
    if not base:
        base = os.environ.get("XDG_CACHE_HOME")
    if not base:
        home = os.path.expanduser("~")
        base = os.path.join(home, ".cache") if home and home != "~" else tempfile.gettempdir()
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        base = tempfile.gettempdir()
    return os.path.join(base, "dims-builder")


def ensure(cache_dir=None, force=False):
    """Return a directory holding the example study, generating it if needed.

    Generation takes a few seconds, almost all of it encoding the two videos,
    and then never happens again: the result is cached under a key that is this
    module's own hash. It is written to a scratch directory and moved into
    place in one step, so an interrupted run leaves no half-study behind that
    the next call would serve.
    """
    root = cache_dir or cache_root()
    out = os.path.join(root, f"example-study-{fingerprint()}")
    if force and os.path.isdir(out):
        shutil.rmtree(out, ignore_errors=True)
    if os.path.isdir(out) and os.path.exists(os.path.join(out, ".complete")):
        return out

    os.makedirs(root, exist_ok=True)
    scratch = tempfile.mkdtemp(prefix="example-study-", dir=root)
    try:
        generate(scratch)
        with open(os.path.join(scratch, ".complete"), "w") as fh:
            fh.write(fingerprint() + "\n")
        shutil.rmtree(out, ignore_errors=True)
        os.replace(scratch, out)
    except BaseException:
        shutil.rmtree(scratch, ignore_errors=True)
        raise
    return out
