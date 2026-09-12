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

  /* The period axis, laid out the way the dashboard's cross-wavelet tab lays it
     out, so that a reader who follows this page and then opens a real study is
     looking at the same picture: a linear axis carrying log2(period), ticked at
     the octaves and labelled in seconds. Long periods are at the top.

     Not `type: "log"` with a reversed autorange, which is the other convention
     and puts the same data upside down. */
  function log2Period(period) {
    return period.map(function (p) { return Math.log2(p); });
  }

  function periodAxis(period) {
    var lo = Math.ceil(Math.log2(Math.min.apply(null, period)));
    var hi = Math.floor(Math.log2(Math.max.apply(null, period)));
    var vals = [], text = [], i, p;
    for (i = lo; i <= hi; i++) {
      p = Math.pow(2, i);
      vals.push(i);
      text.push(p < 1 ? p.toFixed(1) : p.toFixed(0));
    }
    return {
      title: { text: "Period (s)" }, tickmode: "array",
      tickvals: vals, ticktext: text,
      gridcolor: C.line, zeroline: false, linecolor: C.line
    };
  }

  /* A grid of the real period per cell, so the hover can name a period the
     reader recognises while the axis carries its logarithm. `z` is 2-D, so a
     1-D customdata cannot be indexed against it. */
  function periodGrid(z, period) {
    return z.map(function (row, i) {
      return row.map(function () { return period[i]; });
    });
  }

  /* The cone of influence: a shaded region plus its boundary, as the tab draws
     it.

     Where it departs from the tab: the step masks a cell when `scale > coi[t]`,
     and these axes are in period, so the boundary is coi scaled by the same
     period/scale ratio the transform used. Drawing raw `coi` on a period axis --
     which the tab does -- puts the line in the wrong place by 3.3%, small but
     wrong in the direction that flatters the result. */
  function coiTraces(time, coi, period, scales) {
    var ratio = period[0] / scales[0];
    var top = Math.log2(Math.max.apply(null, period));
    var floorP = period[0];
    var y = coi.map(function (c) { return Math.log2(Math.max(c * ratio, floorP)); });
    return [
      { x: time.concat([time[time.length - 1], time[0]]),
        y: y.concat([top, top]),
        type: "scatter", mode: "none", fill: "toself",
        fillcolor: "rgba(0, 0, 0, 0.08)", line: { width: 0 },
        hoverinfo: "skip", showlegend: false, name: "COI" },
      { x: time, y: y, type: "scatter", mode: "lines",
        line: { color: C.text, width: 2, dash: "dash" },
        customdata: coi, showlegend: false, name: "cone of influence",
        hovertemplate: "Time: %{x:.1f}s<br>COI period: %{customdata:.2f}s<extra></extra>" }
    ];
  }

  /* The 95% boundary as a contour of ratio == 1, which is how the payload asks
     to be read: `power / signif_xwt`, `coherence / sig95_wtc`.

     Where it departs from the tab: the tab asks for contours from 0.95 to 1.5
     every 0.5, which draws two lines, at 0.95 and 1.45. One line at the level
     the text describes is what a figure explaining the level should show. */
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
      line: { color: "black", width: 2 }, hoverinfo: "skip"
    };
  }

  function heat(x, y, z, opts) {
    return merge({
      x: x, y: y, z: z, type: "heatmap", colorscale: "Viridis",
      colorbar: { titleside: "top", thickness: 10, outlinewidth: 0,
                  tickfont: { size: 9 } }
    }, opts || {});
  }

  /* Phase as one of eight glyphs, binned as the tab bins it. Right is in phase,
     and the angle turns anticlockwise from there. */
  var GLYPHS = ["→", "↗", "↑", "↖", "←", "↙", "↓", "↘"];

  function phaseGlyph(deg) {
    return GLYPHS[Math.floor(((deg + 22.5) % 360) / 45)];
  }

  /* The glyph trace itself: a dark disc under white text, because the glyphs sit
     on the pale end of Viridis as often as the dark end and neither a light nor
     a dark ink is readable on both. */
  function glyphTrace(x, y, text, customdata) {
    return {
      x: x, y: y, text: text, customdata: customdata,
      type: "scatter", mode: "markers+text",
      marker: { size: 15, color: "rgba(0,0,0,0.45)" },
      textfont: {
        // Arial has no U+2196-2199, so the diagonals would arrive as tofu.
        family: "Segoe UI Symbol, Apple Symbols, DejaVu Sans, sans-serif",
        size: 14, color: "#ffffff"
      },
      textposition: "middle center", showlegend: false,
      hovertemplate: "%{customdata}<extra></extra>"
    };
  }

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
        var y = log2Period(v.period);
        draw(el, [
          heat(v.time, y, z, {
            colorbar: { title: "Power" },
            customdata: periodGrid(z, v.period),
            hovertemplate: "Time: %{x:.1f}s<br>Period: %{customdata:.2f}s<br>" +
                           "Power: %{z:.4f}<extra></extra>"
          }),
          ratioContour(v.time, y, z, v.signif_xwt)
        ].concat(coiTraces(v.time, v.coi, v.period, v.scales)), {
          plot_bgcolor: C.panel,
          xaxis: { title: { text: "Time (s)" }, range: [v.time[0], v.time[v.time.length - 1]] },
          yaxis: periodAxis(v.period)
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
        var y = log2Period(v.period);

        /* Glyphs only where the relationship is above chance and outside the
           cone: a phase read off a cell that means nothing is a decoration.

           Where this departs from the tab: the tab gates its glyphs on *power*
           significance. Phase is only readable where the timing is consistent,
           which is what coherence measures, so the gate here is `sig95_wtc`. */
        var gx = [], gy = [], gt = [], gd = [];
        var skipT = Math.max(1, Math.floor(v.time.length / 20));
        var skipF = Math.max(1, Math.floor(v.period.length / 12));
        for (var i = 0; i < v.period.length; i += skipF) {
          for (var j = 0; j < v.time.length; j += skipT) {
            var c = z[i][j], lvl = v.sig95_wtc ? v.sig95_wtc[i] : null;
            if (c === null || lvl === null || c <= lvl) { continue; }
            if (v.scales[i] > v.coi[j]) { continue; }
            var a = phase[i][j];
            if (a === null) { continue; }
            var deg = (a * 180 / Math.PI + 360) % 360;
            gx.push(v.time[j]);
            gy.push(y[i]);
            gt.push(phaseGlyph(deg));
            gd.push("Time: " + v.time[j].toFixed(1) + "s | Period: " +
                    v.period[i].toFixed(2) + "s<br>Phase: " + deg.toFixed(0) +
                    "°<br>Coherence: " + c.toFixed(3));
          }
        }

        draw(el, [
          heat(v.time, y, z, {
            zmin: 0, zmax: 1,
            colorbar: { title: "Coherence" },
            customdata: periodGrid(z, v.period),
            hovertemplate: "Time: %{x:.1f}s<br>Period: %{customdata:.2f}s<br>" +
                           "Coherence: %{z:.4f}<extra></extra>"
          }),
          ratioContour(v.time, y, z, v.sig95_wtc)
        ].concat(coiTraces(v.time, v.coi, v.period, v.scales),
                 [glyphTrace(gx, gy, gt, gd)]), {
          plot_bgcolor: C.panel,
          xaxis: { title: { text: "Time (s)" }, range: [v.time[0], v.time[v.time.length - 1]] },
          yaxis: periodAxis(v.period)
        }, 380);

        var frac = p.statistics.wtc_signif_fraction;
        caption(el, "Wavelet coherence, with the same cone and the 95% " +
          "<code>sig95_wtc</code> boundary. The glyphs are <code>phase</code>, " +
          "drawn only on above-chance cells outside the cone: → means in phase, " +
          "and here they point consistently at the 4 s band, where " +
          "<code>sig_b</code> lags by 0.7&nbsp;s. The burst at 20–35&nbsp;s is " +
          "bright in power and <em>not</em> here. " +
          (100 * frac).toFixed(1) + "% of usable cells are above chance, against " +
          "the 5% you would get from two unrelated signals.");
      });
    },

    "fig-xwt-global": function (el) {
      return load("demo_crosswavelet.json").then(function (d) {
        var v = xwtPair(d).visualization;
        var y = log2Period(v.period);
        /* The visualization copies, not the `statistics` ones: those are written
           at full resolution and would be a different length from this axis. */
        draw(el, [
          { x: v.global_power, y: y, type: "scatter", mode: "lines",
            name: "global power", line: { color: C.text, width: 2 },
            customdata: v.period,
            hovertemplate: "Power: %{x:.4f}<br>Period: %{customdata:.2f}s<extra></extra>" },
          { x: v.global_signif, y: y, type: "scatter", mode: "lines",
            name: "95% level", line: { color: C.text, width: 1, dash: "dash" },
            customdata: v.period,
            hovertemplate: "95% level: %{x:.4f}<br>Period: %{customdata:.2f}s<extra></extra>" }
        ], {
          plot_bgcolor: C.panel,
          showlegend: true, legend: { orientation: "h", y: 1.14, x: 0 },
          margin: { t: 34 },
          xaxis: { title: { text: "Power" } },
          yaxis: periodAxis(v.period)
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
        var band = p.scale_avg_band;
        draw(el, [
          { x: v.time, y: v.scale_avg_power, type: "scatter", mode: "lines",
            line: { color: C.text, width: 2 }, name: "scale-averaged power",
            hovertemplate: "Time: %{x:.1f}s<br>Power: %{y:.4f}<extra></extra>" },
          { x: [v.time[0], v.time[v.time.length - 1]], y: [lvl, lvl],
            type: "scatter", mode: "lines", name: "95% level",
            line: { color: C.text, width: 1, dash: "dash" },
            hovertemplate: "95% level: %{y:.4f}<extra></extra>" }
        ], {
          plot_bgcolor: C.panel,
          showlegend: true, legend: { orientation: "h", y: 1.14, x: 0 },
          margin: { t: 34 },
          xaxis: { title: { text: "Time (s)" } },
          yaxis: { title: { text: band
            ? band[0].toFixed(1) + "–" + band[1].toFixed(1) + "s avg"
            : "scale-averaged power" } }
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
