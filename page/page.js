// Draws the plots built from the notebook, then loads Python (Pyodide) in the
// background and wires the sliders to the notebook's own functions.
(function () {
  var config = JSON.parse(document.getElementById("page-config").textContent);
  var plotConfig = { responsive: true, displaylogo: false };

  function draw(div, fig) {
    if (!fig) return;
    var layout = Object.assign({}, fig.layout, { autosize: true });
    delete layout.width;
    Plotly.react(div, fig.data, layout, plotConfig);
  }

  // 1. Static plots, straight away.
  document.querySelectorAll("script.fig").forEach(function (el) {
    draw(el.previousElementSibling, JSON.parse(el.textContent));
  });

  var blocks = Array.prototype.slice.call(document.querySelectorAll("[data-live]"));
  if (!blocks.length) return;

  function values(block) {
    var v = {};
    block.querySelectorAll("input, select").forEach(function (el) {
      if (el.type === "checkbox") v[el.name] = el.checked;
      else if (el.type === "range") v[el.name] = Number(el.value);
      else v[el.name] = el.value;
    });
    return v;
  }

  function fail(err) {
    console.error(err);
    blocks.forEach(function (b) {
      b.classList.remove("loading");
      b.classList.add("failed");
      b.querySelector(".status").innerHTML =
        'Couldn’t load Python. <a href="' + document.querySelector("a.button").getAttribute("href") +
        '">Open as notebook</a> instead.';
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
    var live = py.pyimport("live");
    live.install();
    var ns = py.runPython("{'__name__': '__main__'}");
    config.cells.forEach(function (src) { live.run_cell(src, ns); });

    blocks.forEach(function (block) {
      var id = Number(block.dataset.live);
      var plot = block.querySelector(".plot");
      var busy = false, pending = false;
      function update() {
        if (busy) { pending = true; return; }
        busy = true;
        // Let the browser paint the slider before Python runs.
        requestAnimationFrame(function () {
          try {
            draw(plot, JSON.parse(live.call_json(id, JSON.stringify(values(block)))));
          } catch (e) { console.error(e); }
          busy = false;
          if (pending) { pending = false; update(); }
        });
      }
      block.querySelectorAll("input, select").forEach(function (el) {
        el.disabled = false;
        el.addEventListener("input", function () {
          if (el.nextElementSibling && el.nextElementSibling.tagName === "OUTPUT") el.nextElementSibling.value = el.value;
          update();
        });
      });
      block.classList.remove("loading");
    });
  }

  window.addEventListener("load", function () {
    if (typeof loadPyodide === "undefined") return fail("pyodide.js did not load");
    start().catch(fail);
  });
})();
