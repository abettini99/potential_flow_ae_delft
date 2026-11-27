// The page's behaviour, in three steps:
//   1. Draw the Plotly figures that build_page.py stored in the page.
//   2. Start Python in a Web Worker (page/worker.js), so the page never freezes
//      while Python calculates.
//   3. Switch on the sliders and editors. Moving a slider or pressing Run asks
//      the worker to rerun some cells, then redraws their outputs.
(function () {
  var config = JSON.parse(document.getElementById("page-config").textContent);

  // ---- outputs ----------------------------------------------------------------

  function cellEl(i) { return document.querySelector('.cell[data-cell="' + i + '"]'); }

  // A figure made for a given width and height is drawn at the width of its
  // column, with its height scaled to match, so it keeps the shape it was made with.
  function plotHeight(div) {
    if (!div._shape || !div.clientWidth) return null; // not shaped, or folded away
    return Math.min(div._height, Math.round(div.clientWidth * div._shape));
  }

  // After the plot's column changed width (window resized, section opened).
  function refit(div) {
    if (!div._fullLayout) return;
    var height = plotHeight(div);
    if (height && height !== div._fullLayout.height) Plotly.relayout(div, { height: height });
    else Plotly.Plots.resize(div);
  }

  function draw(div, fig) {
    var layout = Object.assign({}, fig.layout, { autosize: true });
    var w = fig.layout && fig.layout.width, h = fig.layout && fig.layout.height;
    div._shape = w && h ? h / w : null;
    div._height = h;
    if (plotHeight(div)) layout.height = plotHeight(div);
    delete layout.width; // fit the page instead
    // fig.show(config=...) in the notebook can change these, e.g. {"displayModeBar": False}
    var config = Object.assign({ responsive: true, displaylogo: false }, fig.config);
    return Plotly.react(div, fig.data, layout, config);
  }

  function pre(cls, text) {
    var p = document.createElement("pre");
    p.className = cls;
    p.textContent = text;
    return p;
  }

  // Replace cell `i`'s outputs with new ones from the worker, without moving the
  // page: the box keeps its height until the new plots are drawn, and existing
  // plots are updated in place rather than removed and drawn again.
  function showOutputs(i, outputs) {
    var box = cellEl(i).querySelector(".outputs");
    var plots = Array.from(box.querySelectorAll(".plot")); // to reuse
    box.style.minHeight = box.offsetHeight + "px";
    box.replaceChildren();
    var drawing = [];
    outputs.forEach(function (out) {
      if (out.type === "text") box.appendChild(pre("output", out.text));
      if (out.type === "error") box.appendChild(pre("output error", out.text));
      if (out.type === "plot") {
        var div = plots.shift() || document.createElement("div");
        div.className = "plot";
        box.appendChild(div);
        drawing.push(draw(div, out.figure));
      }
    });
    Promise.all(drawing).finally(function () { box.style.minHeight = ""; });
  }

  // ---- what to run --------------------------------------------------------------

  // {"Vinf": 2.5, ...}: page/live.py puts these into the cell's "Vinf = ..." lines
  function sliderValues(i) {
    var values = {};
    cellEl(i).querySelectorAll(".sliders input").forEach(function (s) { values[s.name] = Number(s.value); });
    return values;
  }

  // One job for the worker: cell `i`'s code (from its editor, if it has one) and sliders.
  function job(i) {
    var editor = cellEl(i).querySelector("textarea");
    return { cell: i, code: editor ? editor.value : config.cells[i], sliders: sliderValues(i) };
  }

  // Jobs for cell `i` and the next `rerun` cells.
  function jobsFrom(i, rerun) {
    var jobs = [];
    for (var k = i; k <= Math.min(i + rerun, config.cells.length - 1); k++) jobs.push(job(k));
    return jobs;
  }

  // ---- talking to the worker ----------------------------------------------------

  var worker = null;
  var busy = false;    // the worker is running something
  var waiting = null;  // the latest request that came in meanwhile: [i, rerun]

  // Rerun from cell `i`. While the worker is busy, only the latest request is
  // kept, and it runs (with the sliders' values at that moment) when the worker is free.
  function rerun(i, n) {
    if (busy) { waiting = [i, n]; return; }
    var jobs = jobsFrom(i, n);
    jobs.forEach(function (j) { cellEl(j.cell).classList.add("computing"); });
    busy = true;
    worker.postMessage({ type: "run", jobs: jobs });
  }

  function finished(results) {
    results.forEach(function (r) { showOutputs(r.cell, r.outputs); });
    document.querySelectorAll(".cell.computing").forEach(function (c) { c.classList.remove("computing"); });
    busy = false;
    if (waiting) { var w = waiting; waiting = null; rerun(w[0], w[1]); }
  }

  // ---- sliders and editors ------------------------------------------------------

  function cellNumber(el) { return Number(el.closest(".cell").dataset.cell); }

  // Wait until a slider has been still for WAIT ms, so Python calculates for
  // where it stops rather than for every step on the way.
  var WAIT = 150;

  function startSliders(block) {
    var i = cellNumber(block), timer = null;
    block.querySelectorAll("input").forEach(function (s) {
      s.disabled = false;
      s.addEventListener("input", function () {
        s.nextElementSibling.value = s.value; // the number next to the slider
        clearTimeout(timer);
        timer = setTimeout(function () { rerun(i, Number(block.dataset.rerun)); }, WAIT);
      });
      // Let go of the slider after dragging it, so the browser has no reason to
      // scroll back to it (Firefox) when the outputs update.
      s.addEventListener("pointerup", function () { s.blur(); });
    });
    block.classList.remove("loading");
  }

  function startEditor(editor) {
    var i = cellNumber(editor);
    var area = editor.querySelector("textarea");
    function run() { rerun(i, Number(editor.dataset.rerun)); }
    area.disabled = editor.querySelector("button").disabled = false;
    editor.querySelector("button").addEventListener("click", run);
    area.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && e.shiftKey) { e.preventDefault(); run(); }
      if (e.key === "Tab") { e.preventDefault(); area.setRangeText("    ", area.selectionStart, area.selectionEnd, "end"); }
    });
    editor.classList.remove("loading");
  }

  function fitHeight(area) { area.style.height = "auto"; area.style.height = area.scrollHeight + "px"; }

  // ---- start --------------------------------------------------------------------

  // 1. Plots from the build.
  document.querySelectorAll("script.fig").forEach(function (s) {
    draw(s.previousElementSibling, JSON.parse(s.textContent));
  });
  document.querySelectorAll(".editor textarea").forEach(function (area) {
    fitHeight(area);
    area.addEventListener("input", function () { fitHeight(area); });
  });

  // Plots in a folded section were drawn without room; size them when it opens.
  document.querySelectorAll("details.section").forEach(function (d) {
    d.addEventListener("toggle", function () {
      if (d.open) d.querySelectorAll(".plot").forEach(refit);
    });
  });
  var resizing = null;
  window.addEventListener("resize", function () {
    clearTimeout(resizing);
    resizing = setTimeout(function () { document.querySelectorAll(".plot").forEach(refit); }, 100);
  });

  // [words](#name) pointing at a named TikZ diagram: hovering the words (or
  // focusing the link) shows a copy of the drawing next to them.
  var figPopup = null;
  function hideFigure() { if (figPopup) { figPopup.remove(); figPopup = null; } }
  function showFigure(link, fig) {
    hideFigure();
    var svg = fig.querySelector("svg");
    if (!svg) return; // TikZJax hasn't drawn it yet
    figPopup = document.createElement("div");
    figPopup.className = "fig-popup";
    figPopup.appendChild(svg.cloneNode(true));
    document.body.appendChild(figPopup);
    // below the words if it fits, otherwise above; kept inside the window
    var r = link.getBoundingClientRect(), p = figPopup.getBoundingClientRect(), gap = 8;
    var top = r.bottom + gap + p.height <= window.innerHeight ? r.bottom + gap : r.top - gap - p.height;
    var left = Math.min(Math.max(gap, r.left + r.width / 2 - p.width / 2), window.innerWidth - p.width - gap);
    figPopup.style.top = Math.max(gap, top) + "px";
    figPopup.style.left = Math.max(gap, left) + "px";
  }
  document.querySelectorAll('a[href^="#"]').forEach(function (link) {
    var fig = document.getElementById(decodeURIComponent(link.getAttribute("href").slice(1)));
    if (!fig || !fig.classList.contains("tikz")) return;
    link.classList.add("fig-ref");
    link.addEventListener("mouseenter", function () { showFigure(link, fig); });
    link.addEventListener("focus", function () { showFigure(link, fig); });
    link.addEventListener("mouseleave", hideFigure);
    link.addEventListener("blur", hideFigure);
    link.addEventListener("click", function () {
      hideFigure();
      // the diagram may sit in a folded section: open it first
      for (var d = fig.closest("details"); d; d = d.parentElement.closest("details")) d.open = true;
    });
  });
  window.addEventListener("scroll", hideFigure, { passive: true });

  var sliders = document.querySelectorAll(".sliders");
  var editors = document.querySelectorAll(".editor");
  if (!sliders.length && !editors.length) return; // nothing interactive: no need for Python

  function failed(err) {
    console.error(err);
    document.querySelectorAll(".sliders, .editor").forEach(function (b) {
      b.classList.remove("loading");
      b.classList.add("failed");
      b.querySelector(".status").innerHTML =
        'Couldn’t load Python. <a href="' + document.querySelector("a.button").getAttribute("href") +
        '">Open as notebook</a> instead.';
    });
  }

  // 2. Python, in the worker. 3. Once it's ready, switch everything on.
  window.addEventListener("load", function () {
    try {
      worker = new Worker("worker.js", { type: "module" });
    } catch (err) {
      return failed(err);
    }
    worker.onmessage = function (e) {
      if (e.data.type === "ready") { sliders.forEach(startSliders); editors.forEach(startEditor); }
      if (e.data.type === "failed") failed(e.data.error);
      if (e.data.type === "done") finished(e.data.results);
    };
    worker.onerror = failed;
    worker.postMessage({ type: "start", config: config, jobs: jobsFrom(0, config.cells.length) });
  });
})();
