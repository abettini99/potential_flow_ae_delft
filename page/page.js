// The page's behaviour, in three steps:
//   1. Draw the Plotly figures that build_page.py stored in the page.
//   2. Load Python in the browser (Pyodide) and run all the notebook's cells.
//   3. Switch on the sliders and editors. Moving a slider or pressing Run
//      reruns code with page/live.py and redraws that cell's outputs.
(function () {
  var config = JSON.parse(document.getElementById("page-config").textContent);
  var live, ns; // the Python helper module and the notebook's variables, once loaded

  // ---- outputs ----------------------------------------------------------------

  function draw(div, fig) {
    var layout = Object.assign({}, fig.layout, { autosize: true });
    delete layout.width; // fit the page instead
    Plotly.react(div, fig.data, layout, { responsive: true, displaylogo: false });
  }

  function pre(cls, text) {
    var p = document.createElement("pre");
    p.className = cls;
    p.textContent = text;
    return p;
  }

  // Run code for cell number `i` and replace its outputs. Returns false on an error.
  function runCell(i, code) {
    var cell = document.querySelector('.cell[data-cell="' + i + '"]');
    var block = cell.querySelector(".sliders");
    var sliders = JSON.stringify(block ? sliderValues(block) : {});
    var outputs = JSON.parse(live.run_cell_json(code, ns, sliders));
    var box = cell.querySelector(".outputs");
    box.innerHTML = "";
    outputs.forEach(function (out) {
      if (out.type === "text") box.appendChild(pre("output", out.text));
      if (out.type === "error") box.appendChild(pre("output error", out.text));
      if (out.type === "plot") {
        var div = document.createElement("div");
        div.className = "plot";
        box.appendChild(div);
        draw(div, out.figure);
      }
    });
    return !outputs.some(function (out) { return out.type === "error"; });
  }

  // The code of cell `i`: what's in its editor if it has one, else the notebook's.
  function codeOf(i) {
    var editor = document.querySelector('.cell[data-cell="' + i + '"] textarea');
    return editor ? editor.value : config.cells[i];
  }

  // Run cell `i`, then the next `rerun` cells, stopping at the first error.
  function runFrom(i, rerun) {
    var last = Math.min(i + rerun, config.cells.length - 1);
    for (var k = i; k <= last; k++) {
      if (!runCell(k, codeOf(k))) return;
    }
  }

  // ---- sliders and editors ------------------------------------------------------

  function cellNumber(el) { return Number(el.closest(".cell").dataset.cell); }

  // {"Vinf": 2.5, ...}: page/live.py puts these into the cell's "Vinf = ..." lines
  function sliderValues(block) {
    var values = {};
    block.querySelectorAll("input").forEach(function (s) { values[s.name] = Number(s.value); });
    return values;
  }

  // While Python is busy, remember only that another run is wanted.
  function whenFree(fn) {
    var busy = false, again = false;
    return function go() {
      if (busy) { again = true; return; }
      busy = true;
      requestAnimationFrame(function () { // let the slider move on screen first
        try { fn(); } catch (e) { console.error(e); }
        busy = false;
        if (again) { again = false; go(); }
      });
    };
  }

  function startSliders(block) {
    var i = cellNumber(block);
    var update = whenFree(function () { runFrom(i, Number(block.dataset.rerun)); });
    block.querySelectorAll("input").forEach(function (s) {
      s.disabled = false;
      s.addEventListener("input", function () {
        s.nextElementSibling.value = s.value; // the number next to the slider
        update();
      });
    });
    block.classList.remove("loading");
  }

  function startEditor(editor) {
    var i = cellNumber(editor);
    var area = editor.querySelector("textarea");
    var button = editor.querySelector("button");
    function run() {
      button.disabled = true;
      requestAnimationFrame(function () {
        runFrom(i, Number(editor.dataset.rerun));
        button.disabled = false;
      });
    }
    area.disabled = button.disabled = false;
    button.addEventListener("click", run);
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

  var sliders = document.querySelectorAll(".sliders");
  var editors = document.querySelectorAll(".editor");
  if (!sliders.length && !editors.length) return; // nothing interactive: no need for Python

  // 2. Python, in the background.
  async function loadPython() {
    var py = await loadPyodide({ indexURL: config.pyodide });
    var code = config.cells.map(function (c) { return c.replace(/^\s*[%!].*$/gm, ""); }).join("\n");
    await py.loadPackagesFromImports(code); // numpy, scipy, ... as the notebook imports them
    await py.loadPackage("micropip");
    await py.pyimport("micropip").install("plotly==" + config.plotly);
    py.FS.writeFile("/home/pyodide/live.py", config.live_py);
    live = py.pyimport("live");
    ns = py.runPython("{'__name__': '__main__'}");
    config.cells.forEach(function (src, i) { runCell(i, src); });
  }

  // 3. Switch everything on, or say what went wrong.
  window.addEventListener("load", function () {
    loadPython().then(function () {
      sliders.forEach(startSliders);
      editors.forEach(startEditor);
    }).catch(function (err) {
      console.error(err);
      document.querySelectorAll(".sliders, .editor").forEach(function (b) {
        b.classList.remove("loading");
        b.classList.add("failed");
        b.querySelector(".status").innerHTML =
          'Couldn’t load Python. <a href="' + document.querySelector("a.button").getAttribute("href") +
          '">Open as notebook</a> instead.';
      });
    });
  });
})();
