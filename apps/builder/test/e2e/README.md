# End-to-end: the wizard in a real browser

The jsdom suite next door tests what the page does with a config. This one tests
what the *builder* does with a person: it drives all of step 1 to step 5 in
Chromium and then reads the `config.json` that came out.

It exists because of a failure the fast tests could not see. A study was built
with cross-wavelet pairs picked on screen and came out with
`include_crosswavelet: []`, so the analysis never ran — and the first sign of it
was the dashboard's network tab saying no cross-wavelet output existed for the
recording. Every layer looked fine on its own.

```sh
python -m pytest test/e2e -q          # from apps/builder
```

Needs `playwright` and its Chromium (`pip install playwright && playwright
install chromium`). It is skipped, not failed, when either is missing, and it is
not part of the default `pytest` run: it starts a server, generates the example
study and drives a browser, so it takes a minute rather than a second.
