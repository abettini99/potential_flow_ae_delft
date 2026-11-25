// Python for the page, in a (module) Web Worker: a separate thread, so the page keeps
// scrolling and its sliders keep moving while Python calculates.
//
// page.js talks to it with messages:
//   {type: "start", config, jobs}  load Python (Pyodide) and run every cell once
//                                  -> {type: "ready"}, or {type: "failed", error}
//   {type: "run", jobs}            run some cells again
//                                  -> {type: "done", results: [{cell, outputs}, ...]}
// A job is {cell: number, code: "...", sliders: {"Vinf": 2.5, ...}}. Jobs run in
// order and stop at the first error. Each cell's outputs come from page/live.py.

var live, ns; // the helper module (live.py) and the notebook's variables

function runJobs(jobs) {
  var results = [];
  for (var job of jobs) {
    var outputs = JSON.parse(live.run_cell_json(job.code, ns, JSON.stringify(job.sliders)));
    results.push({ cell: job.cell, outputs: outputs });
    if (outputs.some(function (out) { return out.type === "error"; })) break;
  }
  return results;
}

async function start(config, jobs) {
  var { loadPyodide } = await import(config.pyodide + "pyodide.mjs");
  var py = await loadPyodide({ indexURL: config.pyodide });
  var code = config.cells.map(function (c) { return c.replace(/^\s*[%!].*$/gm, ""); }).join("\n");
  await py.loadPackagesFromImports(code); // numpy, scipy, ... as the notebook imports them
  await py.loadPackage("micropip");
  await py.pyimport("micropip").install("plotly==" + config.plotly);
  py.FS.writeFile("/home/pyodide/live.py", config.live_py);
  live = py.pyimport("live");
  ns = py.runPython("{'__name__': '__main__'}");
  runJobs(jobs); // the page already shows these outputs (from the build), so they're not sent back
}

self.onmessage = async function (e) {
  var msg = e.data;
  if (msg.type === "start") {
    try {
      await start(msg.config, msg.jobs);
      postMessage({ type: "ready" });
    } catch (err) {
      postMessage({ type: "failed", error: String(err) });
    }
  }
  if (msg.type === "run") {
    postMessage({ type: "done", results: runJobs(msg.jobs) });
  }
};
