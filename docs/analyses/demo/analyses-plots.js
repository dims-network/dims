/* Figures for the Analyses pages, drawn from real DIMS payloads.
   GENERATED-ADJACENT: this file and the demo_*.json beside it are copied to the
   docs site by tools/render_docs.py. Edit them here, in the core, not there.

   Every figure reads a payload that `docs/analyses/demo/make_demo_data.py`
   produced by running the actual analyses over synthetic signals. Nothing is
   redrawn by hand and nothing is recomputed in the browser: if a field changes
   shape or a level moves, the picture moves with it.

   A page declares a figure by placing <div class="figure" id="fig-..."></div>.
   Only the ids present on the page are built, and each payload is fetched once. */
(function () {
  "use strict";

  /* ---------- the payload encodings, exactly as documented on the overview ---- */

  function decodeF32(o) {
    var raw = Uint8Array.from(atob(o.data), function (c) { return c.charCodeAt(0); });
    var flat = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
    if (o.shape.length === 1) {
      var line = new Array(o.shape[0]);
      for (var k = 0; k < o.shape[0]; k++) {
        line[k] = Number.isNaN(flat[k]) ? null : flat[k];
      }
      return line;
    }
    var rows = o.shape[0], cols = o.shape[1], out = [];
    for (var r = 0; r < rows; r++) {
      var row = new Array(cols);
      for (var c = 0; c < cols; c++) {
        var v = flat[r * cols + c];
        row[c] = Number.isNaN(v) ? null : v;   // Plotly reads null as a gap
      }
      out.push(row);
    }
    return out;
  }

  function decodeBitmap(o) {
    var raw = Uint8Array.from(atob(o.data), function (c) { return c.charCodeAt(0); });
    var stride = (o.cols + 7) >> 3, out = [];
    for (var r = 0; r < o.rows; r++) {
      var row = new Array(o.cols);
      for (var c = 0; c < o.cols; c++) {
        row[c] = (raw[r * stride + (c >> 3)] >> (7 - (c & 7))) & 1;
      }
      out.push(row);
    }
    return out;
  }

  /* ---------- house style, taken from the site's own CSS variables ----------- */

  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return (v && v.trim()) || fallback;
  }

  var C = {
    text: cssVar("--text", "#1f2328"),
    dim: cssVar("--dim", "#8c959f"),
    line: cssVar("--line", "#d9dee3"),
    panel: cssVar("--panel2", "#f6f8fa"),
    teal: cssVar("--web", "#0d9488"),
    purple: cssVar("--py", "#7c3aed"),
    accent: cssVar("--accent", "#0969da"),
    amber: cssVar("--amber", "#9a6700")
  };

  var FONT = { family: "-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif",
               size: 12, color: C.text };

  /* Sequential, light-to-dark, for power and coherence. Perceptually ordered so
     "more" reads as "darker" in greyscale too, which a printed page needs. */
  var SEQ = [[0, "#f7fbfc"], [0.25, "#bfe3e0"], [0.5, "#5fbfb6"],
             [0.75, "#0d9488"], [1, "#134e4a"]];
  /* Cyclic, for phase: -pi and +pi are the same angle and must be the same colour. */
  var CYCLIC = [[0, "#7c3aed"], [0.25, "#0d9488"], [0.5, "#f0f6f6"],
                [0.75, "#9a6700"], [1, "#7c3aed"]];

  function layout(extra) {
    var base = {
      font: FONT,
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "#ffffff",
      margin: { l: 58, r: 16, t: 26, b: 44 },
      hovermode: "closest",
      showlegend: false,
      xaxis: { gridcolor: C.line, zeroline: false, linecolor: C.line },
      yaxis: { gridcolor: C.line, zeroline: false, linecolor: C.line }
    };
    return merge(base, extra || {});
  }

  function merge(a, b) {
    var out = {}, k;
    for (k in a) { out[k] = a[k]; }
    for (k in b) {
      out[k] = (b[k] && typeof b[k] === "object" && !Array.isArray(b[k]) && a[k])
        ? merge(a[k], b[k]) : b[k];
    }
    return out;
  }

  var CONFIG = { displayModeBar: false, responsive: true, displaylogo: false };

  function draw(el, traces, lay, height) {
    el.style.height = (height || 340) + "px";
    return Plotly.newPlot(el, traces, layout(lay), CONFIG);
  }

  function caption(el, text) {
    var p = document.createElement("p");
    p.className = "fig-note";
    p.innerHTML = text;
    el.parentNode.insertBefore(p, el.nextSibling);
  }

  /* ---------- shared trace builders ----------------------------------------- */

  /* The cone of influence, drawn where the analysis actually applies it.

     The step masks a cell when `scale > coi[t]`, and these axes are in period,
     so the boundary is coi scaled by the same period/scale ratio the transform
     used. Drawing raw `coi` on a period axis would put the line in the wrong
     place by 3.3% -- small, but wrong in the direction that matters. */
  function coiTrace(time, coi, period, scales, yTop) {
    var ratio = period[0] / scales[0];
    var x = [time[0]].concat(time, [time[time.length - 1]]);
    var y = [yTop].concat(coi.map(function (c) { return c * ratio; }), [yTop]);
    return {
      x: x, y: y, type: "scatter", mode: "lines", fill: "toself",
      fillcolor: "rgba(31,35,40,0.13)", line: { color: C.text, width: 1, dash: "dot" },
      hoverinfo: "skip", name: "cone of influence"
    };
  }

  /* The 95% boundary as a contour of ratio == 1, which is how the payload asks
     to be read: `power / signif_xwt`, `coherence / sig95_wtc`. */
  function ratioContour(x, y, z, level) {
    var ratio = z.map(function (row, i) {
      return row.map(function (v) {
        return (v === null || level[i] === null) ? null : v / level[i];
      });
    });
    return {
      x: x, y: y, z: ratio, type: "contour", showscale: false,
      autocontour: false,
      contours: { start: 1, end: 1, size: 1, coloring: "none", showlabels: false },
      line: { color: "#111827", width: 1.4 }, hoverinfo: "skip"
    };
  }

  function heat(x, y, z, opts) {
    return merge({
      x: x, y: y, z: z, type: "heatmap", colorscale: SEQ,
      colorbar: { thickness: 11, outlinewidth: 0, len: 0.92, tickfont: { size: 10 } },
      hovertemplate: "%{x:.1f} s · %{y:.2f} s<br>%{z:.3f}<extra></extra>"
    }, opts || {});
  }

  var PERIOD_AXIS = {
    type: "log", autorange: "reversed", title: { text: "period (s)" },
    gridcolor: C.line, zeroline: false, linecolor: C.line
  };

  /* ---------- data, fetched once each ---------------------------------------- */

  var cache = {};
  function load(name) {
    if (!cache[name]) {
      cache[name] = fetch(name).then(function (r) {
        if (!r.ok) { throw new Error(name + ": HTTP " + r.status); }
        return r.json();
      });
    }
    return cache[name];
  }

  function xwtPair(d) { return d.crosswavelet_pairs["sig_a_vs_sig_b"]; }

  /* ---------- the figures ---------------------------------------------------- */

  var FIGURES = {

    "fig-signals": function (el) {
      return load("demo_signals.json").then(function (d) {
        var t = d.time;
        draw(el, [
          { x: t, y: d.series.sig_a, type: "scatter", mode: "lines", name: "sig_a",
            line: { color: C.teal, width: 1.4 } },
          { x: t, y: d.series.sig_b, type: "scatter", mode: "lines", name: "sig_b",
            line: { color: C.purple, width: 1.4 } }
        ], {
          showlegend: true,
          legend: { orientation: "h", y: 1.12, x: 0 },
          margin: { t: 34 },
          xaxis: { title: { text: "time (s)" } },
          yaxis: { title: { text: "value" } },
          shapes: [{ type: "rect", xref: "x", yref: "paper", x0: 20, x1: 35,
                     y0: 0, y1: 1, fillcolor: "rgba(154,103,0,0.09)",
                     line: { width: 0 }, layer: "below" }]
        }, 300);
        caption(el, "The running example. Both signals carry a 4 s oscillation, " +
          "<code>sig_b</code> delayed by 0.7&nbsp;s. The shaded span is the burst " +
          "at 1.20&nbsp;s in <code>sig_a</code> and 1.45&nbsp;s in <code>sig_b</code> — " +
          "joint energy without a stable relationship.");
      });
    },

    "fig-xwt-power": function (el) {
      return load("demo_crosswavelet.json").then(function (d) {
        var p = xwtPair(d), v = p.visualization;
        var z = decodeF32(v.power);
        draw(el, [
          heat(v.time, v.period, z, {
            colorbar: { title: { text: "|W<sup>XY</sup>|", side: "right" },
                        thickness: 11, outlinewidth: 0, len: 0.92,
                        tickfont: { size: 10 } } }),
          ratioContour(v.time, v.period, z, v.signif_xwt),
          coiTrace(v.time, v.coi, v.period, v.scales,
                   v.period[v.period.length - 1])
        ], {
          xaxis: { title: { text: "time (s)" }, range: [v.time[0], v.time[v.time.length - 1]] },
          yaxis: PERIOD_AXIS
        }, 380);
        caption(el, "Cross-wavelet power, <code>visualization.power</code> — a " +
          "<code>f32-b64</code> grid of " + v.power.shape[0] + " periods × " +
          v.power.shape[1] + " times. The black outline is <code>power / " +
          "signif_xwt = 1</code>, the 95% level against red noise; the shaded " +
          "region is the cone of influence, where the transform has run off the " +
          "end of the record.");
      });
    },

    "fig-xwt-coherence": function (el) {
      return load("demo_crosswavelet.json").then(function (d) {
        var p = xwtPair(d), v = p.visualization;
        var z = decodeF32(v.coherence), phase = decodeF32(v.phase);
        var ratio = v.period[0] / v.scales[0];

        /* Arrows only where the relationship is above chance and outside the
           cone: a phase read off a cell that means nothing is a decoration. */
        var arrows = [];
        for (var i = 0; i < v.period.length; i += 3) {
          for (var j = 4; j < v.time.length; j += 10) {
            var c = z[i][j], lvl = v.sig95_wtc ? v.sig95_wtc[i] : null;
            if (c === null || lvl === null || c <= lvl) { continue; }
            if (v.scales[i] > v.coi[j]) { continue; }
            var a = phase[i][j];
            if (a === null) { continue; }
            arrows.push({
              x: v.time[j], y: v.period[i], xref: "x", yref: "y",
              ax: -9 * Math.cos(a), ay: 9 * Math.sin(a),
              axref: "pixel", ayref: "pixel",
              showarrow: true, arrowhead: 2, arrowsize: 1, arrowwidth: 1.1,
              arrowcolor: "rgba(17,24,39,0.75)"
            });
          }
        }

        draw(el, [
          heat(v.time, v.period, z, {
            zmin: 0, zmax: 1,
            colorbar: { title: { text: "R²", side: "right" }, thickness: 11,
                        outlinewidth: 0, len: 0.92, tickfont: { size: 10 } } }),
          ratioContour(v.time, v.period, z, v.sig95_wtc),
          coiTrace(v.time, v.coi, v.period, v.scales,
                   v.period[v.period.length - 1])
        ], {
          xaxis: { title: { text: "time (s)" }, range: [v.time[0], v.time[v.time.length - 1]] },
          yaxis: PERIOD_AXIS,
          annotations: arrows
        }, 380);

        var frac = p.statistics.wtc_signif_fraction;
        caption(el, "Wavelet coherence, with the same cone and the 95% " +
          "<code>sig95_wtc</code> boundary. Arrows are <code>phase</code>, drawn " +
          "only on above-chance cells outside the cone: right means in phase, " +
          "and here they lean consistently at the 4 s band, where " +
          "<code>sig_b</code> lags by 0.7&nbsp;s. The burst at 20–35&nbsp;s is " +
          "bright in power and <em>not</em> here. " +
          (100 * frac).toFixed(1) + "% of usable cells are above chance, against " +
          "the 5% you would get from two unrelated signals.");
      });
    },

    "fig-xwt-global": function (el) {
      return load("demo_crosswavelet.json").then(function (d) {
        var v = xwtPair(d).visualization;
        draw(el, [
          { x: v.global_power, y: v.period, type: "scatter", mode: "lines",
            name: "global power", line: { color: C.teal, width: 2 } },
          { x: v.global_signif, y: v.period, type: "scatter", mode: "lines",
            name: "95% level", line: { color: C.amber, width: 1.6, dash: "dash" } }
        ], {
          showlegend: true, legend: { orientation: "h", y: 1.14, x: 0 },
          margin: { t: 34 },
          xaxis: { title: { text: "time-averaged |W<sup>XY</sup>|" } },
          yaxis: PERIOD_AXIS
        }, 340);
        caption(el, "<code>global_power</code> against <code>global_signif</code>: " +
          "the whole record averaged over time, tested with the degrees of freedom " +
          "that averaging buys (Torrence &amp; Compo eq. 23). The 4 s peak clears " +
          "the level; the burst does not, because it occupies a quarter of the " +
          "record and averaging dilutes it.");
      });
    },

    "fig-xwt-scaleavg": function (el) {
      return load("demo_crosswavelet.json").then(function (d) {
        var p = xwtPair(d), v = p.visualization;
        var lvl = p.statistics.scale_avg_signif;
        draw(el, [
          { x: v.time, y: v.scale_avg_power, type: "scatter", mode: "lines",
            fill: "tozeroy", fillcolor: "rgba(13,148,136,0.16)",
            line: { color: C.teal, width: 1.6 }, name: "scale-averaged power" },
          { x: [v.time[0], v.time[v.time.length - 1]], y: [lvl, lvl],
            type: "scatter", mode: "lines", name: "95% level",
            line: { color: C.amber, width: 1.5, dash: "dash" } }
        ], {
          showlegend: true, legend: { orientation: "h", y: 1.14, x: 0 },
          margin: { t: 34 },
          xaxis: { title: { text: "time (s)" } },
          yaxis: { title: { text: "scale-averaged power" } }
        }, 280);
        caption(el, "<code>scale_avg_power</code> over the band in " +
          "<code>scale_avg_band</code>, one number per time point, against the " +
          "single scalar <code>statistics.scale_avg_signif</code>. This is the " +
          "series to correlate with anything else you measured.");
      });
    },

    "fig-rqa-plot": function (el) {
      return load("demo_rqa.json").then(function (d) {
        var e = d.rqa_data.sig_a, v = e.visualization;
        var m = decodeBitmap(v.matrix);
        draw(el, [
          { x: v.time, y: v.time, z: m, type: "heatmap",
            colorscale: [[0, "#ffffff"], [1, C.teal]], showscale: false,
            hovertemplate: "i = %{y:.1f} s<br>j = %{x:.1f} s<extra></extra>",
            xaxis: "x", yaxis: "y" },
          { x: v.time, y: v.data, type: "scatter", mode: "lines",
            line: { color: C.text, width: 1 }, xaxis: "x", yaxis: "y2",
            hoverinfo: "skip" }
        ], {
          xaxis: { title: { text: "time j (s)" }, domain: [0, 1], anchor: "y",
                   constrain: "domain" },
          yaxis: { title: { text: "time i (s)" }, domain: [0, 0.72], anchor: "x",
                   scaleanchor: "x", scaleratio: 1, constrain: "domain" },
          yaxis2: { domain: [0.78, 1], anchor: "x", title: { text: "sig_a" },
                    gridcolor: C.line, zeroline: false },
          margin: { l: 58, r: 16, t: 12, b: 44 }
        }, 520);
        caption(el, "The recurrence plot of <code>sig_a</code>, " +
          v.matrix.rows + "×" + v.matrix.cols + " after the drawing reduction, " +
          "at a threshold of " + e.threshold.toFixed(4) + " z-score units — the " +
          "distance that makes " + (100 * e.achieved_recurrence).toFixed(1) +
          "% of pairs recurrent. The regular diagonal banding is the 4 s " +
          "oscillation; the texture change between 20 s and 35 s is the burst.");
      });
    },

    "fig-rqa-compare": function (el) {
      return load("demo_rqa.json").then(function (d) {
        var names = ["periodic", "sig_a", "noisy"];
        var titles = ["periodic — a 3 s sine",
                      "sig_a — rhythm plus a burst",
                      "noisy — AR(1), no structure"];
        var traces = [], lay = { margin: { l: 44, r: 10, t: 30, b: 40 },
                                 annotations: [] };
        names.forEach(function (name, k) {
          var v = d.rqa_data[name].visualization;
          var ax = k === 0 ? "" : String(k + 1);
          traces.push({
            x: v.time, y: v.time, z: decodeBitmap(v.matrix), type: "heatmap",
            colorscale: [[0, "#ffffff"], [1, C.teal]], showscale: false,
            hoverinfo: "skip", xaxis: "x" + ax, yaxis: "y" + ax
          });
          var lo = k / 3 + 0.012, hi = (k + 1) / 3 - 0.012;
          lay["xaxis" + ax] = { domain: [lo, hi], anchor: "y" + ax,
                                gridcolor: C.line, zeroline: false,
                                title: { text: "time (s)" } };
          lay["yaxis" + ax] = { domain: [0, 1], anchor: "x" + ax,
                                gridcolor: C.line, zeroline: false,
                                scaleanchor: "x" + ax, scaleratio: 1,
                                showticklabels: k === 0 };
          lay.annotations.push({
            text: titles[k], x: (lo + hi) / 2, y: 1.04, xref: "paper",
            yref: "paper", showarrow: false, font: { size: 11, color: C.dim }
          });
        });
        draw(el, traces, lay, 300);
        caption(el, "The same threshold rule, three signals, all at a 7% " +
          "recurrence rate — the rate is fixed by construction, so what " +
          "distinguishes them is where the recurrent points <em>are</em>. " +
          "A pure oscillation gives long uninterrupted diagonals; red noise " +
          "gives speckle with almost no line longer than one point.");
      });
    },

    "fig-rqa-metrics": function (el) {
      return load("demo_rqa.json").then(function (d) {
        var e = d.rqa_data.sig_a, w = e.windowed_metrics;
        draw(el, [
          { x: w.time, y: w.RR, type: "scatter", mode: "lines", name: "RR",
            line: { color: C.dim, width: 1.4 } },
          { x: w.time, y: w.DET, type: "scatter", mode: "lines", name: "DET",
            line: { color: C.teal, width: 2 } },
          { x: w.time, y: w.LAM, type: "scatter", mode: "lines", name: "LAM",
            line: { color: C.purple, width: 1.6 } },
          { x: w.time, y: w.L_MAX, type: "scatter", mode: "lines", name: "L_MAX (s)",
            line: { color: C.amber, width: 1.6 }, yaxis: "y2" }
        ], {
          showlegend: true, legend: { orientation: "h", y: 1.16, x: 0 },
          margin: { t: 36, r: 52 },
          xaxis: { title: { text: "window centre (s)" } },
          yaxis: { title: { text: "share of recurrent points" }, range: [0, 1.02] },
          yaxis2: { title: { text: "L_MAX (s)" }, overlaying: "y", side: "right",
                    showgrid: false, zeroline: false }
        }, 320);
        caption(el, "<code>windowed_metrics</code>: " + w.time.length +
          " windows of " + e.window.length_used_sec + " s, every " +
          e.window.step_used_sec + " s, plotted at the window centre. RR is flat " +
          "near the global rate; DET and LAM are the ones that move. L_MAX is on " +
          "the right axis because it is in <strong>seconds</strong>, not a share.");
      });
    },

    "fig-crqa-lag": function (el) {
      return load("demo_crqa.json").then(function (d) {
        var e = d.crqa_data.lead_vs_lag, v = e.visualization;
        draw(el, [
          { x: v.time, y: v.time, z: decodeBitmap(v.matrix), type: "heatmap",
            colorscale: [[0, "#ffffff"], [1, C.purple]], showscale: false,
            hovertemplate: "lead i = %{y:.1f} s<br>lag j = %{x:.1f} s<extra></extra>" },
          { x: [v.time[0], v.time[v.time.length - 1] - 2],
            y: [v.time[0] + 2, v.time[v.time.length - 1]],
            type: "scatter", mode: "lines", hoverinfo: "skip",
            line: { color: C.amber, width: 1.2, dash: "dash" } }
        ], {
          xaxis: { title: { text: "time in lag (s)" }, constrain: "domain" },
          yaxis: { title: { text: "time in lead (s)" }, scaleanchor: "x",
                   scaleratio: 1, constrain: "domain" }
        }, 420);
        caption(el, "<code>lead</code> against <code>lag</code>, the same signal " +
          "2 s apart. The recurrent band sits on the dashed line, offset from the " +
          "diagonal by exactly the delay. Rows index the first series, columns the " +
          "second. Note what the payload does <em>not</em> contain: nothing in it " +
          "reports “2 s”. The offset is visible and unquantified.");
      });
    },

    "fig-crqa-pair": function (el) {
      return load("demo_crqa.json").then(function (d) {
        var e = d.crqa_data.sig_a_vs_sig_b, v = e.visualization, w = e.windowed_metrics;
        draw(el, [
          { x: v.time, y: v.time, z: decodeBitmap(v.matrix), type: "heatmap",
            colorscale: [[0, "#ffffff"], [1, C.purple]], showscale: false,
            hovertemplate: "sig_a i = %{y:.1f} s<br>sig_b j = %{x:.1f} s<extra></extra>",
            xaxis: "x", yaxis: "y" },
          { x: w.time, y: w.DET, type: "scatter", mode: "lines", name: "DET",
            line: { color: C.teal, width: 2 }, xaxis: "x2", yaxis: "y2" },
          { x: w.time, y: w.LAM, type: "scatter", mode: "lines", name: "LAM",
            line: { color: C.purple, width: 1.5 }, xaxis: "x2", yaxis: "y2" }
        ], {
          showlegend: true, legend: { orientation: "h", y: 1.06, x: 0.55 },
          margin: { l: 54, r: 14, t: 26, b: 44 },
          xaxis: { domain: [0, 0.5], anchor: "y", title: { text: "sig_b (s)" },
                   gridcolor: C.line, zeroline: false, constrain: "domain" },
          yaxis: { domain: [0, 1], anchor: "x", title: { text: "sig_a (s)" },
                   gridcolor: C.line, zeroline: false, scaleanchor: "x",
                   scaleratio: 1, constrain: "domain" },
          xaxis2: { domain: [0.62, 1], anchor: "y2", gridcolor: C.line,
                    zeroline: false, title: { text: "window centre (s)" } },
          yaxis2: { domain: [0, 1], anchor: "x2", gridcolor: C.line,
                    zeroline: false, range: [0, 1.02] }
        }, 380);
        caption(el, "The running example as a cross-recurrence plot, beside its " +
          "windowed metrics. The windows are square blocks on the main diagonal, " +
          "so these numbers describe cells near it — what the two signals do at " +
          "the <em>same</em> moment, not at a lag.");
      });
    }
  };

  /* ---------- build whatever this page asked for ----------------------------- */

  function fail(el, err) {
    el.innerHTML = '<p class="fig-error">This figure could not be drawn: ' +
      String(err && err.message ? err.message : err) + "</p>";
  }

  function run() {
    var wanted = Object.keys(FIGURES).filter(function (id) {
      return document.getElementById(id);
    });
    if (!wanted.length) { return; }
    if (typeof Plotly === "undefined") {
      wanted.forEach(function (id) {
        fail(document.getElementById(id), new Error("Plotly did not load"));
      });
      return;
    }
    wanted.forEach(function (id) {
      var el = document.getElementById(id);
      try {
        Promise.resolve(FIGURES[id](el)).catch(function (e) { fail(el, e); });
      } catch (e) { fail(el, e); }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else { run(); }
})();
