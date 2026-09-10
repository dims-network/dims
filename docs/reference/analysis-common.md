# `dims_analysis.common` — the shared machinery

Fourteen modules that the analysis steps share. Nothing here is an analysis; it is
the plumbing every step needs, factored out so that a rule exists **once**.

This is contributor reference. If you are writing a step, read
[`contracts/step.md`](../contracts/step.md) first — it tells you which of these to
reach for. This page is what each one actually offers.

> Grouped on one page rather than fourteen, because none of these is looked up by
> name from outside the package.

---

## Payload encoding and precision

### `arrays` — the two wire encodings
`PAYLOAD_VERSION = 2`, `BITMAP = "bitmap-b64"`, `FLOAT32 = "f32-b64"`.

`pack_bitmap(matrix)` / `unpack_bitmap(obj)` — one bit per cell, rows byte-aligned.
`pack_f32` / `unpack_f32` — little-endian float32, NaN preserved.
`is_packed(obj)`, `unpack(obj)` — dispatch without knowing which encoding you have.
`nan_to_none(values)` — for the plain-list fields, since JSON has no NaN.

The browser's half of this contract is
[`DIMS.decodeArray`](dims-api.md).

### `payload` — significant figures, and saying what produced a file
`PAYLOAD_SIGNIFICANT_FIGURES = 6`.

`round_significant(x)` and `round_payload(obj)` round to **significant figures, not
decimal places** — a coherence of `0.0000123` and a power of `12345.6` cannot share
a decimal count without one of them being destroyed.

`provenance(**extra)` returns `{"core_version": …}` plus whatever the step adds,
dropping `None`s. `precision_note()` records how the file was rounded.

An output that does not say how it was made cannot be compared with another. Two
real cases drove this: a study computed partly at 100 surrogates and partly at 300
was silently inconsistent, and a recurrence analysis that *reached* 33.7 % against
a 7 % target looked identical to one that was *asked for* 33.7 %.

### `results` — merging rather than clobbering
`VERSION_KEY`, `UnversionedPayload`, `check_version`, `same_version`,
`merge_payload`, `read_existing`, `compare_entries`, `write_payload(path, payload,
compact=True)`.

Re-running one pair must not delete the other pairs already in the file, and a
payload from a different format version must not be merged into one that is not.

---

## Reading input

### `series` — loading a time series, with the failures named
`TIME = "Time"`, `SeriesError`.

`time_column(df)` finds the time column case-insensitively.
`load(path, min_points=0, value_column=None, min_variance=None)` raises
`SeriesError` with a sentence saying what is wrong.
`load_or_none(...)` is the same for the steps that want to warn and continue.
`normalise(values)` is the z-normalisation the recurrence analyses run on.

### `assets` — where a private study's data actually is
`MARKER = 'data.local.json'`.

`assets_root(project_dir)`, `resolve(path, project_dir, root)`, `describe(...)`.
A private study keeps recordings outside the repository; this is the one place
that knows how to follow the pointer. See
[`contracts/data-visibility.md`](../contracts/data-visibility.md).

### `config` — reading the `include_*` keys
`ConfigError`, `gate_value`, `enabled(config, key)`,
`as_list(config, key, what)`, `tuning(config, step_id)`,
`tuned_number(config, step_id, key, default)`.

Three keys use three different conventions — a list of measures, a list of pairs,
a boolean — so the reading of them lives here rather than being re-guessed per
step. `as_list` raises with an example of the right shape rather than a type error.

### `limits` — refusing what will not fit
`MIN_POINTS = 10`, `MIN_VARIANCE = 0.0`, `MAX_MATRIX_BYTES = 2 GiB`,
`InputTooLarge`.

`matrix_bytes(n)`, `max_points(budget)`, `check_length(n, what, budget)`.

A recurrence matrix is quadratic and `cdist` returns float64, so 8 bytes a cell —
which puts the ceiling near **16,000 points**. Being told that before the
allocation is better than an `OOM` twenty minutes in.

---

## Recurrence

### `recurrence` — one definition of every recurrence quantity
`RATE_TOLERANCE = 0.01`.

| | |
|---|---|
| `threshold_for_target(distance_matrix, target, self_paired)` | the threshold that hits a target recurrence rate |
| `rate_report(target, achieved, tolerance)` | the warning when it could not |
| `recurrence_rate(matrix, self_paired)` | the rate |
| `line_lengths(matrix, direction, min_len, self_paired)` | diagonal or vertical runs |
| `window_metrics(matrix, dt, min_line, self_paired)` | `(RR, DET, LAM, L_MAX)` |

**`self_paired` is the whole point of this module.** A plain recurrence plot
compares a series with itself, so the line of identity is trivially recurrent and
must be excluded from every count; a cross-recurrence plot compares two different
series, so there is no line of identity and nothing to exclude. Getting that wrong
shifts every number. One flag, one implementation, both steps.

`L_MAX` is returned in **seconds** — the longest run multiplied by `dt`.

### `reduce` — making a picture small without lying about it
`factor_for(n_points, max_points)` — **rounds up**, so the result never exceeds the
cap.
`block_mean`, `block_mode`, `block_binary`, `rate_of(m)`.

`block_binary` is the one that matters: it keeps both the structure and the
density, selecting blocks **by rank** rather than by a density threshold, so the
output rate is exact rather than depending on where a quantile lands among ties.
A recurrent line stays a line.

`rate_of` is a plain mean and **includes** the line of identity, unlike
`recurrence.recurrence_rate` — the two numbers in a payload are close but not
identical, and they are not measuring quite the same thing.

### `window` — sliding windows that fit the recording
`MIN_WINDOWS = 20`, `MIN_WINDOW_POINTS = 2`, `WindowPlan`, `plan(n, dt, window_sec,
step_sec, min_windows)`.

A long window over a short recording gives a handful of windows and no time
course, so `plan` shortens what it must — and the two limits are separate:

- **The window length** is capped at half the recording's span (with a floor of two
  samples). `MIN_WINDOWS` plays no part in that.
- **The step** is then shortened, if necessary, so that `MIN_WINDOWS` of them fit
  across what is left to slide over.

A 20-second window with a 1-second step over a 30-second recording comes back as
**15 s windows at a 0.75 s step, 21 of them** — both values adjusted, and the
warning says so: *"the 20 s window was shortened to 15 s and the 1 s step was
shortened to 0.75 s, because a 30 s recording cannot hold 20 of the requested
windows."*

`WindowPlan.report()` records **asked-for beside used**, so the payload never hides
the substitution — and DET and LAM depend on the window length, so an adjusted
analysis is not comparable with an unadjusted one.

---

## Wavelet

### `coherence` — smoothing, delegated deliberately
`smoothed_spectra(W1, W2, scales, dt, dj, mother_wavelet)`,
`coherence_from_spectra(S1, S2, S12)`, `coherence(...)`.

The smoothing operator is pycwt's, validated, rather than a local
reimplementation. That is not incidental: a hand-rolled smoother that failed to
cancel phase is exactly the defect that shipped once and was found by a notebook
rather than a crash.

### `tc98` — Torrence & Compo (1998), transcribed
`DEFAULT_LEVEL = 0.95`, `Z1_95_PUBLISHED = 2.182`, `Z2_95_PUBLISHED = 3.999`,
`MAX_DIRECT_NU = 60.0`.

`cross_wavelet_pdf`, `survival`, `survival_by_quadrature`, `cross_wavelet_z(nu,
level)`, `ar1_background(alpha, period, dt)`, `local_significance`,
`time_average_dof`, `time_average_significance`, `scale_average_dof`,
`scale_average_significance`.

The two `_PUBLISHED` constants are the paper's own numbers, kept so the derived
values can be **checked against print**. `tests/reference/test_wavelet_reference.py`
does check `cross_wavelet_z` against 2.182 and 3.999 — though it restates those
figures itself rather than importing these constants, so the constants here are
documentation rather than something a test consumes. The
distinction between the four significance levels — and which question each answers
— is on [the cross-wavelet page](../analyses/crosswavelet.md).

---

## Step plumbing

### `step_io` — the parts of a step that are always the same
`parse_args(prog, description, default_output_dir, argv)`,
`tuning(config, step_id, window_sec, step_sec, target_recurrence_default)`,
`resolve_io(input_dir, output_dir, project_dir)`,
`payload_writer(output_dir, output_name, label)`,
`report_merge(report)`.

`parse_args` defaults `--window` and `--step` to `None` rather than to a number,
**deliberately**: `None` means "the config decides", and a default here would
silently win over the study's own `analysis` block.

### `manifest` — what a complete `assets/` looks like
`NAME = 'MANIFEST.json'`, `scan`, `path_for`, `load`, `write(project_dir,
deep=True)`, `compare(project_dir, deep=False)` → `(missing, changed, extra)`.

Driven by [`dims-analysis manifest`](cli/dims-analysis.md#manifest). Skips
`MANIFEST.json` itself, `.gitkeep` and `.DS_Store`; hashes in 1 MiB chunks.

## See also

- [`contracts/step.md`](../contracts/step.md) — writing a step.
- [`contracts/analysis-output.md`](../contracts/analysis-output.md) — the rules
  these modules exist to enforce, each with the measurement behind it.
