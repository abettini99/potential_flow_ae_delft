"""Runs notebook code cells outside Jupyter.

The same file is used twice: by build_page.py when the site is built (normal
Python) and inside the web page (Python in the browser, via Pyodide). Both run
every cell in one shared namespace, like a notebook kernel does.

A cell's outputs are collected as a list of dicts:
    {"type": "text",  "text": ...}     anything printed, or the value of the last line
    {"type": "plot",  "figure": ...}   a Plotly figure (fig.show() or the last line)
    {"type": "error", "text": ...}     the traceback, only in run_cell_json
"""
import ast
import contextlib
import io
import json
import re
import sys
import traceback
import types

_outputs = None  # outputs of the cell that is running

SLIDER_RE = re.compile(r"\s*#\s*page:slider\s*\((.*)\)\s*")  # "# page:slider (0.5, 5.0, 0.1)"
ASSIGN_RE = re.compile(r"\s*([A-Za-z_]\w*)\s*=\s*(.+?)\s*")  # "Vinf = 1" on the next line


def _show(fig, *args, **kwargs):
    """Replaces Plotly's fig.show(): keep the figure instead of opening it."""
    if _outputs is not None:
        _outputs.append({"type": "plot", "figure": json.loads(fig.to_json())})


def find_sliders(src):
    """{"Vinf": ((0.5, 5.0, 0.1), "1", line number)} for each "# page:slider (min, max, step)"
    with "Vinf = 1" on the line below it."""
    lines, found = src.splitlines(), {}
    for i, line in enumerate(lines):
        if m := SLIDER_RE.fullmatch(line):
            a = ASSIGN_RE.fullmatch(lines[i + 1]) if i + 1 < len(lines) else None
            if not a:
                raise ValueError(f"put 'name = value' on the line under '{line.strip()}'")
            found[a.group(1)] = (ast.literal_eval(f"({m.group(1)})"), a.group(2), i + 1)
    return found


def set_sliders(src, values):
    """The cell's code with each slider's "name = ..." line set to the slider's value."""
    lines = src.splitlines()
    for name, ((lo, hi, step), _, i) in find_sliders(src).items():
        if name in values:
            value = values[name]
            if any(isinstance(x, float) for x in (lo, hi, step)):
                value = float(value)  # a 0.1-step slider at 2 gives 2.0, not 2
            indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
            lines[i] = f"{indent}{name} = {value!r}"
    return "\n".join(lines)


def clean(src):
    """The code to run and show: without %pip/!shell lines and page markers."""
    skip = ("%", "!", "# page:", "#page:", "# rerun=", "#rerun=")
    return "\n".join(l for l in src.splitlines() if not l.lstrip().startswith(skip))


def run_cell(src, ns, sliders=None):
    """Run one cell in namespace `ns` and return its outputs. Errors are raised.
    `sliders` ({"Vinf": 2.5}) replaces the values written under "# page:slider" lines."""
    global _outputs
    import plotly.graph_objects as go
    import plotly.io as pio
    from plotly.basedatatypes import BaseFigure
    BaseFigure.show = _show
    # The page is dark: figures default to Plotly's dark look on a see-through
    # background. Colours a cell sets itself still win.
    if "page" not in pio.templates:
        page = go.layout.Template(pio.templates["plotly_dark"])  # a copy
        page.layout.paper_bgcolor = page.layout.plot_bgcolor = "rgba(0,0,0,0)"
        pio.templates["page"] = page
    pio.templates.default = "page"
    # ipywidgets doesn't exist in the browser; the page has its own sliders.
    sys.modules.setdefault("ipywidgets", types.ModuleType("ipywidgets"))

    if sliders:
        src = set_sliders(src, sliders)
    _outputs = outputs = []
    tree = ast.parse(clean(src))
    # Like Jupyter: if the last line is an expression, its value is shown.
    last = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
    printed = io.StringIO()
    try:
        with contextlib.redirect_stdout(printed):
            exec(compile(tree, "<cell>", "exec"), ns)
            if last is not None and not clean(src).rstrip().endswith(";"):
                value = eval(compile(ast.Expression(last.value), "<cell>", "eval"), ns)
                if isinstance(value, BaseFigure):
                    _show(value)
                elif value is not None:
                    print(repr(value))
    finally:
        _outputs = None
    if printed.getvalue():
        outputs.insert(0, {"type": "text", "text": printed.getvalue()})
    return outputs


def run_cell_json(src, ns, sliders_json="{}"):
    """For the page: run a cell, return its outputs as JSON, errors included."""
    try:
        outputs = run_cell(src, ns, json.loads(sliders_json))
    except Exception as err:
        # Only show the lines of the traceback that point into the cell itself.
        frames = [f for f in traceback.extract_tb(err.__traceback__) if f.filename == "<cell>"]
        text = "".join(traceback.format_list(frames) + traceback.format_exception_only(type(err), err))
        outputs = [{"type": "error", "text": text.strip()}]
    return json.dumps(outputs)

