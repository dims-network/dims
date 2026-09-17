# DIMS documentation

DIMS puts every signal from a recorded session on one timeline, beside the video
and transcript they came from, with the analyses that say how two signals relate.
Click a peak in a time series and the video jumps to the moment that produced it.

It is for researchers who **already have time-aligned measures** — motion
tracking, physiology, gaze codes, annotation tiers — and want to get from a
statistical pattern back to the raw record that produced it.

**What DIMS is not:** it is not a preprocessing pipeline. It does not clean
signals, estimate synchrony, or align clocks. It displays what you give it, which
means it displays a misaligned signal faithfully as a misaligned signal.

**The video is optional.** The core is driven by timestamps, not by a recording —
a study with no `.mp4` anywhere still gets the time series, RQA, cross-RQA,
cross-wavelet and ELAN tabs, all on the same timeline. That covers foot-pressure
and other insole sensing, audio-only corpora, motion capture, EMG, eye-tracking,
and any study whose video was stripped for de-identification. What you lose is the
video panel and the ability to click from a peak to the moment on screen; nothing
else changes.

**[See a live dashboard →](https://dims-network.github.io/case-demo/)** Click the
timeline; the video and every chart follow.

This site is for two kinds of reader: researchers who want to explore their own
recordings with DIMS, and contributors who want to add a tab, an analysis, or a
fix. The nav above splits along that line — **Welcome** and **For no-code
dashboard** get you to your first dashboard without writing code; **Overview of
existing analysis modules** shows what DIMS already computes; **Extending DIMS**
is the contracts and reference material for changing the code itself.

---

Published at **<https://dims-network.github.io/dims/>**, built from this
directory once per release — a page on the site and the file beside the code are
the same text, at the version you are reading. See [Citing DIMS](citing.md) for
the paper and the code.
