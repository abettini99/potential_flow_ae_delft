"""Run notebook code outside Jupyter: at build time (CPython) and in the web page (Pyodide).

Stands in for `ipywidgets` so that the same notebook code works three ways:
in JupyterLite (real ipywidgets), when the page is built, and live in the page.
Supported: interact / interact as a decorator, FloatSlider, IntSlider, Dropdown,
Checkbox, and the (min, max, step) / list / bool shorthands.
Plotly figures are captured from fig.show() or from a cell's last expression.
"""
import ast
import contextlib
import inspect
import io
import json
import sys

IN_BROWSER = sys.platform == "emscripten"
_interacts = []   # (function, controls) in the order the notebook creates them
_outputs = None   # output list of the cell being run, or None


# ---- widgets -------------------------------------------------------------

class _Control:
    kind = ""

    def __init__(self, value=None, description="", **kw):
        self.value = value
        self.description = description
        self.options = kw

    def spec(self, name):
        d = {"name": name, "kind": self.kind, "label": self.description or name, "value": self.value}
        d.update(self.options)
        return d


class FloatSlider(_Control):
    kind = "slider"

    def __init__(self, value=None, min=0.0, max=10.0, step=0.1, description="", **kw):
        value = (min + max) / 2 if value is None else value
        super().__init__(value, description, min=min, max=max, step=step)


class IntSlider(FloatSlider):
    def __init__(self, value=None, min=0, max=100, step=1, description="", **kw):
        value = (min + max) // 2 if value is None else value
        super().__init__(value, min, max, step, description)


class Dropdown(_Control):
    kind = "dropdown"

    def __init__(self, options=(), value=None, description="", **kw):
        options = list(options)
        super().__init__(options[0] if value is None and options else value, description, choices=options)


class Checkbox(_Control):
    kind = "checkbox"

    def __init__(self, value=False, description="", **kw):
        super().__init__(bool(value), description)


def _control(v):
    if isinstance(v, _Control):
        return v
    if isinstance(v, bool):
        return Checkbox(v)
    if isinstance(v, tuple) and len(v) in (2, 3):
        lo, hi = v[0], v[1]
        step = v[2] if len(v) == 3 else None
        if all(isinstance(x, int) for x in v):
            return IntSlider(min=lo, max=hi, step=step or 1)
        return FloatSlider(min=lo, max=hi, step=step or (hi - lo) / 100)
    if isinstance(v, (list, dict)):
        return Dropdown(list(v))
    return None  # a fixed argument


def interact(f=None, **kwargs):
    if f is None:
        return lambda g: interact(g, **kwargs)
    controls, fixed = {}, {}
    try:
        defaults = {k: p.default for k, p in inspect.signature(f).parameters.items()
                    if p.default is not inspect.Parameter.empty}
    except (TypeError, ValueError):
        defaults = {}
    for name, v in kwargs.items():
        c = _control(v)
        if c is None:
            fixed[name] = v
            continue
        # Like ipywidgets: a shorthand starts at the function's default value.
        if not isinstance(v, _Control) and name in defaults:
            c.value = defaults[name]
        controls[name] = c
    func = (lambda **vals: f(**fixed, **vals)) if fixed else f
    index = len(_interacts)
    _interacts.append(func)
    spec = {"id": index, "controls": [c.spec(n) for n, c in controls.items()]}
    if not IN_BROWSER:
        spec["figure"] = call(index, {n: c.value for n, c in controls.items()})
    _emit({"type": "live", **spec})
    return f


# ---- outputs -------------------------------------------------------------

def _emit(out):
    if _outputs is not None:
        _outputs.append(out)


def _figure_json(fig):
    return json.loads(fig.to_json())


def _patch_plotly():
    try:
        from plotly.basedatatypes import BaseFigure
    except ImportError:
        return
    BaseFigure.show = lambda self, *a, **k: _emit({"type": "plot", "figure": _figure_json(self)})


def call(index, values):
    """Run interact function `index` with `values`; return the figure it made, or None."""
    global _outputs
    saved, _outputs = _outputs, []
    try:
        result = _interacts[index](**values)
        if result is not None and hasattr(result, "to_json"):
            _emit({"type": "plot", "figure": _figure_json(result)})
        figs = [o["figure"] for o in _outputs if o["type"] == "plot"]
    finally:
        _outputs = saved
    return figs[-1] if figs else None


def call_json(index, values_json):
    """Page entry point: JSON in, JSON out."""
    return json.dumps(call(index, json.loads(values_json)))


# ---- running cells -------------------------------------------------------

def strip_magics(src):
    return "\n".join(l for l in src.splitlines() if not l.lstrip().startswith(("%", "!")))


def run_cell(src, ns):
    """Execute one code cell like Jupyter would; return its outputs."""
    global _outputs
    _patch_plotly()
    _outputs = outs = []
    tree = ast.parse(strip_magics(src))
    last = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(tree, "<cell>", "exec"), ns)
            if last is not None:
                value = eval(compile(ast.Expression(last.value), "<cell>", "eval"), ns)
                quiet = strip_magics(src).rstrip().endswith(";")
                if value is None or quiet or callable(value):
                    pass  # interact() returns the function; Jupyter's repr of it is noise here
                elif hasattr(value, "to_json"):
                    _emit({"type": "plot", "figure": _figure_json(value)})
                else:
                    print(repr(value))
    finally:
        _outputs = None
    if buf.getvalue():
        outs.insert(0, {"type": "text", "text": buf.getvalue()})
    return outs


def install():
    """Make `import ipywidgets` resolve to this module."""
    sys.modules["ipywidgets"] = sys.modules[__name__]
