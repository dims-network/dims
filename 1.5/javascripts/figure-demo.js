/* The figures on the figure-geometry page, drawn by the file that page is about.
 *
 * `figure-geometry.js` is published into this site from packages/dims-tabs/ and
 * loaded before this script, so what you see here is the release's own geometry
 * rather than a drawing of it: move HAND_Y in the source and this picture moves.
 * The same rule as the analyses pages, where every figure is real output.
 *
 * The drawing conventions -- edges under nodes, TAB_NODE_R dots, labels 16 units
 * below them -- are the dashboard tab's, from packages/dims-tabs/network.js. The
 * tab's own logic is not reimplemented here: this page shows the body and the
 * fan, and the tab's page shows the tab.
 */
(function () {
  "use strict";

  var SVG_NS = "http://www.w3.org/2000/svg";

  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return (v && v.trim()) || fallback;
  }

  var C = {
    text: cssVar("--text", "#1f2328"),
    dim: cssVar("--dim", "#8c959f"),
    teal: cssVar("--web", "#0d9488"),
    purple: cssVar("--py", "#7c3aed")
  };

  /* The caller's element-maker. appendFigure takes one because the tab and the
     wizard each already have their own; this is the third consumer. */
  function el(name, attrs) {
    var node = document.createElementNS(SVG_NS, name);
    Object.keys(attrs || {}).forEach(function (k) {
      node.setAttribute(k, attrs[k]);
    });
    return node;
  }

  /* The tab's frame. The network tab draws in exactly this, and fig-people uses
     it unchanged; fig-body extends below it to fit two rows of annotation under
     a foot that sits at 545, and marks where the tab's picture would end. */
  var TAB_VIEW_H = 560;

  function svgFor(host, viewH, maxPx) {
    var svg = el("svg", {
      viewBox: "0 0 1000 " + viewH,
      width: "100%",
      role: "img",
      style: "display:block;max-height:" + (maxPx || 420) + "px;height:auto"
    });
    host.appendChild(svg);
    return svg;
  }

  function labelRows(y, rows) {
    var out = [];
    for (var i = 0; i < rows; i++) { out.push(y + 16 + i * 17); }
    return out;
  }

  function label(svg, x, y, text, opts) {
    var o = opts || {};
    var t = el("text", {
      x: x, y: y, "text-anchor": o.anchor || "middle",
      fill: o.fill || C.text, "font-size": o.size || 13,
      "font-weight": o.weight || 400
    });
    t.textContent = text;
    svg.appendChild(t);
    return t;
  }

  function note(host, html) {
    var p = document.createElement("p");
    p.className = "fig-note";
    p.innerHTML = html;
    host.parentNode.insertBefore(p, host.nextSibling);
  }

  /* ---------- the figures --------------------------------------------------- */

  var FIGURES = {
    /* One body with every place on it, named and numbered. Derived from SPOTS,
       so a place added to the source appears here without touching the page. */
    "fig-body": function (host) {
      var G = window.DIMS_FIGURE;
      var svg = svgFor(host, 650, 470);
      var cx = 500;

      G.appendFigure(svg, { cx: cx, color: C.teal, el: el, opacity: 0.22 });

      var at = G.positions(cx);
      G.SPOTS.forEach(function (sp) {
        var p = at[sp.part];
        svg.appendChild(el("circle", {
          cx: p.x, cy: p.y, r: G.TAB_NODE_R, fill: C.teal, opacity: 0.9
        }));
        var rows = labelRows(p.y + G.TAB_NODE_R, 2);
        label(svg, p.x, rows[0], sp.label, { weight: 700 });
        label(svg, p.x, rows[1],
              "dx " + (sp.dx > 0 ? "+" : "") + sp.dx + " · y " + sp.y,
              { fill: C.dim, size: 11 });
      });

      /* The centre line the dx values are measured from. */
      svg.appendChild(el("line", {
        x1: cx, y1: 30, x2: cx, y2: TAB_VIEW_H, stroke: C.dim,
        "stroke-width": 1, "stroke-dasharray": "4 6", opacity: 0.7
      }));
      label(svg, cx + 8, 44, "centre line, x = " + cx,
            { anchor: "start", fill: C.dim, size: 11 });

      /* Where the tab's picture stops. The foot's annotation is below it, which
         is exactly why the tab has no room to label anything down there. */
      svg.appendChild(el("line", {
        x1: 40, y1: TAB_VIEW_H, x2: 960, y2: TAB_VIEW_H, stroke: C.dim,
        "stroke-width": 1, "stroke-dasharray": "2 6", opacity: 0.8
      }));
      label(svg, 960, TAB_VIEW_H - 8, "the tab's viewBox ends at y " + TAB_VIEW_H,
            { anchor: "end", fill: C.dim, size: 11 });

      note(host, "The six places in <code>SPOTS</code>, on a figure centred at " +
        "500. Dots are drawn at <code>TAB_NODE_R</code>, the dashboard's radius; " +
        "the wizard uses the larger <code>NODE_R</code> because there the circle " +
        "is a drop target. The dashed rule is the bottom of the tab's " +
        "<code>0 0 1000 560</code> viewBox — this diagram reaches past it to " +
        "label a foot that sits at y 545, and the tab cannot.");
    },

    /* Two people with measures on them, as the network tab arranges them. */
    "fig-people": function (host) {
      var G = window.DIMS_FIGURE;
      var svg = svgFor(host, TAB_VIEW_H, 460);   // the tab's frame, unchanged

      var people = [
        { label: "Teacher", prefix: "teacher_", color: C.teal },
        { label: "Student", prefix: "student_", color: C.purple }
      ];
      var measures = ["righthandspeed", "lefthandspeed", "nosespeed"];

      /* Bodies first, then edges, then nodes -- the tab's order, so a node is
         never hidden under the line that arrives at it. */
      people.forEach(function (person, i) {
        person.cx = G.personCx(i, people.length);
        person.at = G.positions(person.cx);
        G.appendFigure(svg, {
          cx: person.cx, color: person.color, el: el, opacity: 0.22
        });
      });

      /* One pair per measure, each person's to the other's -- the shape of a
         study's include_crosswavelet list. The part is read out of the name by
         the same bodyPart() the tab uses on a study's measures. */
      var pairs = measures.map(function (m) {
        return {
          name: m,
          a: people[0].at[G.bodyPart(people[0].prefix + m)],
          b: people[1].at[G.bodyPart(people[1].prefix + m)]
        };
      });
      var ranks = G.bowRanks(pairs.length);
      var step = G.bowStep(pairs.length);
      pairs.forEach(function (pair, i) {
        svg.appendChild(el("path", {
          d: G.edgePath(pair.a, pair.b, ranks[i], step),
          fill: "none", stroke: C.text, "stroke-linecap": "round",
          "stroke-width": 3, opacity: 0.5
        }));
      });

      people.forEach(function (person) {
        measures.forEach(function (m) {
          var p = person.at[G.bodyPart(person.prefix + m)];
          svg.appendChild(el("circle", {
            cx: p.x, cy: p.y, r: G.TAB_NODE_R, fill: person.color, opacity: 0.9
          }));
          label(svg, p.x, labelRows(p.y + G.TAB_NODE_R, 1)[0],
                G.spot(G.bodyPart(m)).label);
        });
        label(svg, person.cx, 40, person.label,
              { fill: person.color, size: 16, weight: 700 });
      });

      note(host, "Two figures at <code>personCx(0, 2)</code> and " +
        "<code>personCx(1, 2)</code> — evenly spaced, with a margin at each end " +
        "— and one edge per pair, fanned by <code>bowRanks</code> so that three " +
        "lines across the same gap stay three lines. This is the arrangement " +
        "the <a href=\"../../tabs/network/\">cross-effector network</a> draws; " +
        "there the width of each edge is the measurement.");
    }
  };

  /* ---------- build whatever this page asked for ---------------------------- */

  function fail(host, err) {
    host.innerHTML = '<p class="fig-error">This figure could not be drawn: ' +
      String(err && err.message ? err.message : err) + "</p>";
  }

  function run() {
    var wanted = Object.keys(FIGURES).filter(function (id) {
      return document.getElementById(id);
    });
    if (!wanted.length) { return; }
    if (!window.DIMS_FIGURE) {
      wanted.forEach(function (id) {
        fail(document.getElementById(id),
             new Error("figure-geometry.js did not load"));
      });
      return;
    }
    wanted.forEach(function (id) {
      var host = document.getElementById(id);
      if (host.dataset.drawn) { return; }
      try {
        FIGURES[id](host);
        host.dataset.drawn = "1";
      } catch (e) { fail(host, e); }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else { run(); }
  /* Material navigates without reloading, so bind to its page stream too. */
  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(run);
  }
})();
