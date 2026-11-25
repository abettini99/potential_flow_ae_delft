"""Turn content/potential_flow.ipynb into a web page in the homepage's style.

    python build_page.py dist/index.html

The notebook's code is run here first, so the page opens with every plot already
drawn. The page then loads Python in the browser (Pyodide) and runs the same
code again, after which the sliders call the notebook's own functions live.

Code is shown by default. A first line "# page:<word>" changes that:
  # page:hide   run the cell but don't show its code (output still shows)
  # page:fold   show the code folded behind a "Code" toggle
  # page:edit   readers can edit the code and run it on the page
  "# @interact(Vinf=(0.5, 5, 0.1), angle=(-30, 30, 1))" as a cell's first line
  shows sliders above its code; moving one sets the variables, reruns the cell
  and every code cell below ("rerun=N" after the parentheses limits that).
  "# @param" lines (Colab form syntax) become sliders/checkboxes/dropdowns;
  moving one sets the variable and reruns every code cell below (or N with
  a "# page: rerun=N" first line). The cell's code isn't shown.
  # page:edit rerun=2   ...and Run also reruns the next 2 code cells below it
                        (hidden cells count), so their plots update;
                        rerun=all reruns every code cell below
Notebook tags still work: remove-cell (show nothing), remove-input (= hide).
Colab's "Hide code" counts as hide.

Interactive parts are written with ipywidgets.interact and Plotly, see
page/live.py for what is supported.
"""
import ast
import html
import json
import re
import sys
from pathlib import Path

import nbformat
import plotly
from nbconvert.filters.markdown_mistune import markdown2html_mistune
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "page"))
import live  # noqa: E402

NOTEBOOK = ROOT / "content" / "potential_flow.ipynb"
NOTEBOOK_URL = "notebooks/index.html?path=potential_flow.ipynb"
PYODIDE_VERSION = "314.0.7"


def script_json(obj):
    return json.dumps(obj).replace("</", "<\\/")


def render_controls(controls):
    rows = []
    for c in controls:
        name = html.escape(c["name"])
        label = html.escape(str(c["label"]))
        if c["kind"] == "slider":
            field = (f'<input type="range" name="{name}" min="{c["min"]}" max="{c["max"]}" '
                     f'step="{c["step"]}" value="{c["value"]}" disabled>'
                     f'<output>{c["value"]}</output>')
        elif c["kind"] == "dropdown":
            opts = "".join(
                f'<option value="{i}"{" selected" if o == c["value"] else ""}>{html.escape(str(o))}</option>'
                for i, o in enumerate(c["choices"]))
            field = (f'<select name="{name}" data-choices="{html.escape(json.dumps(c["choices"]))}" '
                     f'disabled>{opts}</select>')
        elif c["kind"] == "number":
            field = f'<input type="number" name="{name}" value="{c["value"]}" step="any" disabled>'
        else:
            checked = " checked" if c["value"] else ""
            field = f'<input type="checkbox" name="{name}"{checked} disabled>'
        rows.append(f'<label class="control"><span>{label}</span>{field}</label>')
    return "".join(rows)


STATUS = ('<span class="status" title="Loading Python so the controls work">'
          '<span class="spinner"></span>Loading</span>')


def render_live(out):
    fig = script_json(out["figure"]) if out["figure"] else "null"
    return (
        f'<div class="live loading" data-live="{out["id"]}">'
        '<div class="controls">' + render_controls(out["controls"]) + STATUS + '</div>'
        f'<div class="plot"></div><script type="application/json" class="fig">{fig}</script></div>'
    )


# Colab's form syntax:  Vinf = 1  # @param {type:"slider", min:0.5, max:5, step:0.1}
PARAM_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*(.+?)\s*#\s*@param\b\s*(.*)$")


def parse_params(src):
    """Controls for the "# @param" lines of a cell (slider, number, boolean, list)."""
    params = []
    for line in src.splitlines():
        m = PARAM_RE.match(line)
        if not m:
            continue
        name, rhs, spec = m.group(1), m.group(2), m.group(3).strip()
        try:
            value = ast.literal_eval(rhs)
        except (ValueError, SyntaxError):
            continue
        if spec.startswith("["):
            params.append({"name": name, "label": name, "kind": "dropdown",
                           "choices": ast.literal_eval(spec), "value": value})
            continue
        opts = {k: v.strip("\"'") for k, v in re.findall(r"(\w+)\s*:\s*(\"[^\"]*\"|'[^']*'|[^,}\s]+)", spec)}
        kind = opts.get("type", "raw")
        num = lambda k, d: ast.literal_eval(opts[k]) if k in opts else d
        if kind == "slider":
            p = {"kind": "slider", "min": num("min", 0), "max": num("max", 10), "step": num("step", 1)}
            p["float"] = any(isinstance(x, float) for x in (p["min"], p["max"], p["step"], value))
        elif kind == "boolean":
            p = {"kind": "checkbox"}
        elif kind in ("number", "integer"):
            p = {"kind": "number", "float": kind == "number"}
        else:
            continue  # strings, dates, raw: not shown as controls
        p.update(name=name, label=name, value=value)
        params.append(p)
    return params


# A comment line in the style of ipywidgets' decorator, above plain code:
#   # @interact(Vinf=(0.5, 5.0, 0.1), angle=(-30, 30, 1))  rerun=2
INTERACT_RE = re.compile(r"^\s*#\s*@interact\s*\((.*)\)\s*(.*)$")


def parse_interact(src, ns):
    """Controls from a "# @interact(...)" first line, or None.

    Each control starts at the variable's current value when an earlier cell
    defined it (and that value fits), else where ipywidgets would start it."""
    lines = [l for l in src.splitlines() if l.strip()]
    m = INTERACT_RE.match(lines[0]) if lines else None
    if not m:
        return None
    try:
        call = ast.parse(f"f({m.group(1)})", mode="eval").body
        kwargs = {k.arg: ast.literal_eval(k.value) for k in call.keywords}
    except (SyntaxError, ValueError) as e:
        raise SystemExit(f"Can't read '{lines[0].strip()}': {e}")
    params = []
    for name, v in kwargs.items():
        c = live._control(v)
        if c is None:
            raise SystemExit(f"'{lines[0].strip()}': {name}= needs (min, max, step), a list or True/False")
        spec = c.spec(name)
        current = ns.get(name)
        if spec["kind"] == "slider":
            spec["float"] = any(isinstance(x, float) for x in v)
            if isinstance(current, (int, float)) and spec["min"] <= current <= spec["max"]:
                spec["value"] = float(current) if spec["float"] else current
        elif spec["kind"] == "dropdown" and current in spec["choices"]:
            spec["value"] = current
        elif spec["kind"] == "checkbox" and isinstance(current, bool):
            spec["value"] = current
        params.append(spec)
    marks = set(m.group(2).replace(",", " ").split())
    return params, marks


def render_params(params, rerun, run_self=False):
    floats = [p["name"] for p in params if p.get("float")]
    return (f'<div class="params loading" data-rerun="{rerun}"{" data-self" if run_self else ""} '
            f'data-floats="{html.escape(json.dumps(floats))}">'
            '<div class="controls">' + render_controls(params) + STATUS + '</div></div>')


def render_output(out):
    if out["type"] == "text":
        return f'<pre class="output">{html.escape(out["text"])}</pre>'
    if out["type"] == "plot":
        return f'<div class="plot"></div><script type="application/json" class="fig">{script_json(out["figure"])}</script>'
    if out["type"] == "live":
        return render_live(out)
    return ""


def page_marks(src):
    """Words from a first line like "# page:edit" (several: "# page:edit fold")."""
    first = src.lstrip().split("\n", 1)[0].strip().lower().replace("# ", "#", 1)
    return set(first[len("#page:"):].replace(",", " ").split()) if first.startswith("#page:") else set()


def rerun_count(marks, default=0):
    """N from "rerun=N": how many code cells below an edit cell run again after it."""
    for m in marks:
        if m == "rerun=all":
            return 1_000_000  # every code cell below
        if m.startswith("rerun="):
            try:
                return max(0, int(m[len("rerun="):]))
            except ValueError:
                raise SystemExit(f"'# page: {m}': rerun needs a whole number or 'all', like rerun=2")
    return default


def build(nb):
    live.install()
    ns = {"__name__": "__main__"}
    parts, code_cells, title = [], [], None
    lexer, fmt = PythonLexer(), HtmlFormatter(cssclass="highlight")
    for cell in nb.cells:
        tags = set(cell.metadata.get("tags", []))
        if cell.cell_type == "code":
            code_cells.append(cell.source)
            interact = parse_interact(cell.source, ns)
            if interact:  # start the variables at the sliders' values
                ns.update({p["name"]: p["value"] for p in interact[0]})
            outputs = live.run_cell(cell.source, ns)
            if "remove-cell" in tags:
                continue
            block = []
            marks = page_marks(cell.source)
            # Colab's "Hide code" (Form menu) stores cellView = "form"
            hidden = ("hide" in marks or "remove-input" in tags
                      or cell.metadata.get("cellView") == "form")
            code = live.strip_magics(cell.source)
            params = parse_params(cell.source)
            if interact:
                # sliders above the cell's code; moving one reruns this cell and the cells below
                block.append(render_params(interact[0], rerun_count(marks | interact[1], default=1_000_000),
                                           run_self=True))
                if code.strip() and not hidden:
                    block.append(f'<details class="code" open><summary>Code</summary>'
                                 f'{highlight(code, lexer, fmt)}</details>')
            elif params:
                # sliders instead of code; moving one reruns the cells below (all by default)
                block.append(render_params(params, rerun_count(marks, default=1_000_000)))
            elif "edit" in marks:
                block.append(
                    f'<div class="editor loading" data-rerun="{rerun_count(marks)}">'
                    f'<textarea spellcheck="false" rows="{code.count(chr(10)) + 1}" disabled>{html.escape(code)}</textarea>'
                    '<div class="editor-bar"><button type="button" disabled>Run</button>'
                    '<span class="status"><span class="spinner"></span>Loading Python</span>'
                    '<span class="hint">Edit the code, then Run (or Shift+Enter)</span></div></div>')
            elif code.strip() and not hidden:
                opened = "" if ("fold" in marks or "hide-input" in tags) else " open"
                block.append(f'<details class="code"{opened}><summary>Code</summary>'
                             f'{highlight(code, lexer, fmt)}</details>')
            rendered = "".join(render_output(o) for o in outputs)
            if rendered or "edit" in marks:
                block.append(f'<div class="outputs">{rendered}</div>')
            if any(block):
                parts.append(f'<div class="cell" data-cell="{len(code_cells) - 1}">' + "".join(block) + "</div>")
        elif cell.cell_type == "markdown" and "remove-cell" not in tags:
            src = cell.source.lstrip()
            if title is None and src.startswith("# "):
                first, _, rest = src.partition("\n")
                title = first[2:].strip()
                parts.append(f"<header><h1>{html.escape(title)}</h1>{markdown2html_mistune(rest)}</header>")
                parts.append(f'<p><a class="button" href="{NOTEBOOK_URL}">Open as notebook</a>'
                             '<span class="hint">to change the code and run it yourself</span></p>')
            else:
                parts.append(f"<section>{markdown2html_mistune(cell.source)}</section>")
    return title or "Potential flow", "\n".join(parts), code_cells


def main(dest, notebook=NOTEBOOK):
    nb = nbformat.read(notebook, as_version=4)
    title, body, code_cells = build(nb)
    config = {
        "pyodide": f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/",
        "plotly": plotly.__version__,
        "cells": code_cells,
        "live_py": (ROOT / "page" / "live.py").read_text(),
    }
    page = (ROOT / "page" / "template.html").read_text()
    for key, value in {
        "{{title}}": html.escape(title),
        "{{plotly_js}}": plotly.offline.get_plotlyjs_version(),
        "{{pyodide}}": config["pyodide"],
        "{{config}}": script_json(config),
        "{{body}}": body,
    }.items():
        page = page.replace(key, value)
    css = (ROOT / "page" / "style.css").read_text()
    css += "\n/* code highlighting */\n" + HtmlFormatter(style="friendly").get_style_defs(".highlight")
    css += "\n@media (prefers-color-scheme: dark) {\n" + HtmlFormatter(style="monokai").get_style_defs(".highlight") + "\n}\n"
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page)
    (dest.parent / "style.css").write_text(css)
    (dest.parent / "page.js").write_text((ROOT / "page" / "page.js").read_text())


if __name__ == "__main__":
    main(*sys.argv[1:2] or ["dist/index.html"], *sys.argv[2:3])
