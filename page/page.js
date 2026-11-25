// Draws the plots built from the notebook, then loads Python (Pyodide) in the
// background, wires the sliders to the notebook's own functions and enables
// the "# page:edit" cells.
(function () {
  var config = JSON.parse(document.getElementById("page-config").textContent);
  var plotConfig = { responsive: true, displaylogo: false };
  var notebookHref = (document.querySelector("a.button") || {}).getAttribute
    ? document.querySelector("a.button").getAttribute("href") : "notebooks/";
  var live = null; // the Python module, once loaded

  function draw(div, fig) {
    if (!fig) return;
    var layout = Object.assign({}, fig.layout, { autosize: true });
    delete layout.width;
    Plotly.react(div, fig.data, layout, plotConfig);
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  // ---- slider blocks ------------------------------------------------------

  function values(block) {
    var v = {};
    block.querySelectorAll(".controls input, .controls select").forEach(function (i) {
      if (i.type === "checkbox") v[i.name] = i.checked;
      else if (i.type === "range") v[i.name] = Number(i.value);
      else v[i.name] = i.value;
    });
    return v;
  }

  function wire(block) {
    var id = Number(block.dataset.live);
    var plot = block.querySelector(".plot");
    var busy = false, pending = false;
    function update() {
      if (busy) { pending = true; return; }
      busy = true;
      requestAnimationFrame(function () { // let the slider repaint first
        try {
          draw(plot, JSON.parse(live.call_json(id, JSON.stringify(values(block)))));
        } catch (e) { console.error(e); }
        busy = false;
        if (pending) { pending = false; update(); }
      });
    }
    block.querySelectorAll(".controls input, .controls select").forEach(function (i) {
      i.disabled = false;
      i.addEventListener("input", function () {
        var out = i.nextElementSibling;
        if (out && out.tagName === "OUTPUT") out.value = i.value;
        update();
      });
    });
    block.classList.remove("loading");
  }

  // Same markup as render_live() in build_page.py, for blocks made by edited cells.
  function liveBlock(spec) {
    var block = el("div", "live loading");
    block.dataset.live = spec.id;
    var controls = el("div", "controls");
    spec.controls.forEach(function (c) {
      var label = el("label", "control");
      label.appendChild(el("span", null, c.label));
      var input;
      if (c.kind === "slider") {
        input = el("input");
        input.type = "range";
        input.min = c.min; input.max = c.max; input.step = c.step; input.value = c.value;
        label.appendChild(input);
        input.name = c.name;
        label.appendChild(el("output", null, String(c.value)));
      } else if (c.kind === "dropdown") {
        input = el("select");
        c.choices.forEach(function (o) {
          var opt = el("option", null, String(o));
          if (o === c.value) opt.selected = true;
          input.appendChild(opt);
        });
        input.name = c.name;
        label.appendChild(input);
      } else {
        input = el("input");
        input.type = "checkbox";
        input.checked = !!c.value;
        input.name = c.name;
        label.appendChild(input);
      }
      controls.appendChild(label);
    });
    block.appendChild(controls);
    var plot = el("div", "plot");
    block.appendChild(plot);
    return { block: block, plot: plot };
  }

  function renderOutputs(container, outs) {
    container.innerHTML = "";
    outs.forEach(function (o) {
      if (o.type === "text") container.appendChild(el("pre", "output", o.text));
      else if (o.type === "error") container.appendChild(el("pre", "output error", o.text));
      else if (o.type === "plot") {
        var div = el("div", "plot");
        container.appendChild(div);
        draw(div, o.figure);
      } else if (o.type === "live") {
        var b = liveBlock(o);
        container.appendChild(b.block);
        draw(b.plot, o.figure);
        wire(b.block);
      }
    });
  }

  // ---- editable cells -----------------------------------------------------

  function enableEditor(ed, ns) {
    var area = ed.querySelector("textarea");
    var button = ed.querySelector("button");
    var outputs = ed.parentNode.querySelector(".outputs");
    function fit() { area.style.height = "auto"; area.style.height = area.scrollHeight + "px"; }
    function run() {
      button.disabled = true;
      button.textContent = "Running…";
      requestAnimationFrame(function () {
        try {
          renderOutputs(outputs, JSON.parse(live.run_cell_json(area.value, ns)));
        } catch (e) {
          renderOutputs(outputs, [{ type: "error", text: String(e) }]);
        }
        button.disabled = false;
        button.textContent = "Run";
      });
    }
    area.disabled = false;
    button.disabled = false;
    area.addEventListener("input", fit);
    area.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && e.shiftKey) { e.preventDefault(); run(); }
      else if (e.key === "Tab" && !e.shiftKey) {
        e.preventDefault();
        var s = area.selectionStart;
        area.setRangeText("    ", s, area.selectionEnd, "end");
        fit();
      }
    });
    button.addEventListener("click", run);
    fit();
    ed.classList.remove("loading");
  }

  // ---- start up -----------------------------------------------------------

  // 1. Plots from the build, straight away.
  document.querySelectorAll("script.fig").forEach(function (s) {
    draw(s.previousElementSibling, JSON.parse(s.textContent));
  });
  document.querySelectorAll(".editor textarea").forEach(function (a) {
    a.style.height = a.scrollHeight + "px";
  });

  var blocks = Array.prototype.slice.call(document.querySelectorAll("[data-live]"));
  var editors = Array.prototype.slice.call(document.querySelectorAll(".editor"));
  if (!blocks.length && !editors.length) return;

  function fail(err) {
    console.error(err);
    blocks.concat(editors).forEach(function (b) {
      b.classList.remove("loading");
      b.classList.add("failed");
      b.querySelector(".status").innerHTML =
        "Couldn’t load Python. <a href=\"" + notebookHref + "\">Open as notebook</a> instead.";
    });
  }

  // 2. Python in the background.
  async function start() {
    var py = await loadPyodide({ indexURL: config.pyodide });
    var all = config.cells.join("\n");
    await py.loadPackagesFromImports(all.split("\n").filter(function (l) {
      return !/^\s*[%!]/.test(l);
    }).join("\n"));
    if (/\bplotly\b/.test(all)) {
      await py.loadPackage("micropip");
      await py.pyimport("micropip").install("plotly==" + config.plotly);
    }
    py.FS.writeFile("/home/pyodide/live.py", config.live_py);
    live = py.pyimport("live");
    live.install();
    var ns = py.runPython("{'__name__': '__main__'}");
    config.cells.forEach(function (src) { live.run_cell(src, ns); });
    blocks.forEach(wire);
    editors.forEach(function (ed) { enableEditor(ed, ns); });
  }

  window.addEventListener("load", function () {
    if (typeof loadPyodide === "undefined") return fail("pyodide.js did not load");
    start().catch(fail);
  });
})();
