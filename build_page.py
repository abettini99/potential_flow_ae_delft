"""Turn content/potential_flow.ipynb into a web page in the homepage's style.

    python build_page.py dist/index.html

The notebook's code is run here first, so the page opens with every plot already
drawn. The page then loads Python in the browser (Pyodide) and runs the same
code again, after which the sliders call the notebook's own functions live.

Code is shown by default. A first line "# page:<word>" changes that:
  # page:hide   run the cell but don't show its code (output still shows)
  # page:fold   show the code folded behind a "Code" toggle
  # page:edit   readers can edit the code and run it on the page
Notebook tags still work: remove-cell (show nothing), remove-input (= hide).
Colab's "Hide code" counts as hide.

Interactive parts are written with ipywidgets.interact and Plotly, see
page/live.py for what is supported.
"""
import html
import json
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


def render_live(out):
    rows = []
    for c in out["controls"]:
        name = html.escape(c["name"])
        label = html.escape(str(c["label"]))
        if c["kind"] == "slider":
            field = (f'<input type="range" name="{name}" min="{c["min"]}" max="{c["max"]}" '
                     f'step="{c["step"]}" value="{c["value"]}" disabled>'
                     f'<output>{c["value"]}</output>')
        elif c["kind"] == "dropdown":
            opts = "".join(
                f'<option{" selected" if o == c["value"] else ""}>{html.escape(str(o))}</option>'
                for o in c["choices"])
            field = f'<select name="{name}" disabled>{opts}</select>'
        else:
            checked = " checked" if c["value"] else ""
            field = f'<input type="checkbox" name="{name}"{checked} disabled>'
        rows.append(f'<label class="control"><span>{label}</span>{field}</label>')
    fig = script_json(out["figure"]) if out["figure"] else "null"
    return (
        f'<div class="live loading" data-live="{out["id"]}">'
        '<div class="controls">' + "".join(rows) +
        '<span class="status" title="Loading Python so the sliders work">'
        '<span class="spinner"></span>Loading</span></div>'
        f'<div class="plot"></div><script type="application/json" class="fig">{fig}</script></div>'
    )


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


def build(nb):
    live.install()
    ns = {"__name__": "__main__"}
    parts, code_cells, title = [], [], None
    lexer, fmt = PythonLexer(), HtmlFormatter(cssclass="highlight")
    for cell in nb.cells:
        tags = set(cell.metadata.get("tags", []))
        if cell.cell_type == "code":
            code_cells.append(cell.source)
            outputs = live.run_cell(cell.source, ns)
            if "remove-cell" in tags:
                continue
            block = []
            marks = page_marks(cell.source)
            # Colab's "Hide code" (Form menu) stores cellView = "form"
            hidden = ("hide" in marks or "remove-input" in tags
                      or cell.metadata.get("cellView") == "form")
            code = live.strip_magics(cell.source)
            if "edit" in marks:
                block.append(
                    f'<div class="editor loading" data-cell="{len(code_cells) - 1}">'
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
                parts.append('<div class="cell">' + "".join(block) + "</div>")
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
