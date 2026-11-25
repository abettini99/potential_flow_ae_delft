"""Turn content/potential_flow.ipynb into the site's front page.

    python build_page.py dist/index.html

How it works:
  1. Every code cell is run here, in order (page/live.py), so the page opens
     with all text, maths and plots already in place.
  2. The page (page/page.js, page/worker.js) then loads Python in the browser and runs the same
     cells again, so sliders and editable cells can rerun code live.

What readers see is set by comments in a code cell. At its top (several can be stacked):
  (nothing)                    code shown, then its output
  # page:hide                  output only, no code
  # page:fold                  code folded behind a "Code" toggle
  # page:edit                  code in an editor with a Run button
  # page:edit rerun=2          ...Run also reruns the next 2 code cells
  # page:rerun=2               for a cell with sliders: rerun only the next 2
                               cells when a slider moves (default: all below)
Anywhere in a cell (the hidden code still runs):
  # page:hide-from             hide the code from here...
  # page:hide-to               ...to here (without it: to the end of the cell)
Anywhere in a cell, a slider for the variable on the next line:
  # page:slider (0.5, 5.0, 0.1)
  Vinf = 1                     (min, max, step); the value is where it starts
Headings fold: a markdown heading (## ...) folds everything below it, up to the
next heading of the same or a higher level. Sections start open; put
<!-- page:closed --> in the heading's cell to start it folded.
Outputs are anything printed and Plotly figures (fig.show() or a figure on the
last line).
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
ALL = 1_000_000  # "rerun=all"



# ---- reading a cell's markers -------------------------------------------------

def read_first_line(src):
    """What the marker lines at the top of a cell ask for, e.g. "# page:edit rerun=2"
    -> {"edit": True, "rerun": 2}. Several can be stacked: "# page:rerun=1" then "# page:hide"."""
    opts = {}
    for line in src.strip().splitlines():
        line = line.strip()
        words = line.lstrip("#").strip().removeprefix("page:").split()
        if not line:
            continue
        if (not line.startswith("#") or not words or words[0] == "slider"
                or not all(w in ("hide", "fold", "edit") or w.startswith("rerun=") for w in words)):
            break  # code, a slider or an ordinary comment: the markers are over
        for word in words:
            if word.startswith("rerun="):
                n = word[len("rerun="):]
                if not (n == "all" or n.isdigit()):
                    raise SystemExit(f"'{line}': rerun= needs a number or 'all'")
                opts["rerun"] = ALL if n == "all" else int(n)
            else:
                opts[word] = True
    return opts


def read_sliders(src):
    """{name: (min, max, step, start value)} for the cell's "# page:slider" lines."""
    try:
        found = live.find_sliders(src)
    except (ValueError, SyntaxError) as err:
        raise SystemExit(f"slider: {err}")
    sliders = {}
    for name, (limits, value, _) in found.items():
        try:
            lo, hi, step = limits
            value = ast.literal_eval(value)
        except (ValueError, TypeError, SyntaxError):
            raise SystemExit(f"slider {name}: write '# page:slider (min, max, step)' above '{name} = number'")
        sliders[name] = (lo, hi, step, min(max(value, lo), hi))  # start inside the range
    return sliders


def shown_code(src):
    """The cell's code without the lines between "# page:hide-from" and "# page:hide-to"."""
    shown, hiding = [], False
    for line in src.splitlines():
        marker = line.replace(" ", "").strip()
        if marker == "#page:hide-from":
            hiding = True
        elif marker == "#page:hide-to":
            hiding = False
        elif not hiding:
            shown.append(line)
    return live.clean("\n".join(shown)).strip()


# ---- HTML pieces ---------------------------------------------------------------

LOADING = '<span class="status"><span class="spinner"></span>Loading Python</span>'


def html_outputs(outputs):
    parts = []
    for out in outputs:
        if out["type"] == "text":
            parts.append(f'<pre class="output">{html.escape(out["text"])}</pre>')
        elif out["type"] == "plot":
            fig = json.dumps(out["figure"]).replace("</", "<\\/")
            parts.append(f'<div class="plot"></div><script type="application/json" class="fig">{fig}</script>')
    return f'<div class="outputs">{"".join(parts)}</div>'


def html_code(code, folded):
    pretty = highlight(code, PythonLexer(), HtmlFormatter(cssclass="highlight"))
    return f'<details class="code"{"" if folded else " open"}><summary>Code</summary>{pretty}</details>'


def html_editor(code, rerun):
    return (f'<div class="editor loading" data-rerun="{rerun}">'
            f'<textarea spellcheck="false" disabled>{html.escape(code)}</textarea>'
            '<div class="bar"><button type="button" disabled>Run</button>' + LOADING +
            '<span class="hint">Edit the code, then Run (or Shift+Enter)</span></div></div>')


def html_sliders(sliders, rerun):
    rows = "".join(
        f'<label class="control"><span>{name}</span>'
        f'<input type="range" name="{name}" min="{lo}" max="{hi}" step="{step}" value="{value}" disabled>'
        f'<output>{value}</output></label>'
        for name, (lo, hi, step, value) in sliders.items())
    return f'<div class="sliders loading" data-rerun="{rerun}">{rows}{LOADING}</div>'


# ---- the page ------------------------------------------------------------------

HEADING_RE = re.compile(r"(#{1,6})\s+\S.*")
CLOSED = "<!-- page:closed -->"  # in a heading's markdown cell: its section starts folded


def build(nb):
    ns = {"__name__": "__main__"}
    parts, cells, title = [], [], None
    # Like Colab, each heading (after the title) folds everything below it up to
    # the next heading of the same or a higher level: text, code, sliders, plots.
    levels = []  # the heading levels of the sections we're inside

    def close_sections(level):
        while levels and levels[-1] >= level:
            parts.append("</div></details>")
            levels.pop()

    for cell in nb.cells:
        if cell.cell_type == "markdown":
            src = cell.source.strip()
            first, _, rest = src.partition("\n")
            if title is None and src.startswith("# "):  # the notebook's title
                title = first[2:]
                parts.append(f"<header><h1>{html.escape(title)}</h1>{markdown2html_mistune(rest)}</header>"
                             f'<p><a class="button" href="{NOTEBOOK_URL}">Open as notebook</a></p>')
            elif m := HEADING_RE.fullmatch(first.strip()):  # a new section
                level = len(m.group(1))
                close_sections(level)
                levels.append(level)
                is_open = "" if CLOSED in src else " open"
                parts.append(f'<details class="section"{is_open}><summary>{markdown2html_mistune(first)}</summary>'
                             '<div class="section-body">')
                if rest.replace(CLOSED, "").strip():
                    parts.append(f"<section>{markdown2html_mistune(rest.replace(CLOSED, ''))}</section>")
            else:
                parts.append(f"<section>{markdown2html_mistune(src)}</section>")
            continue

        index = len(cells)
        cells.append(cell.source)
        opts = read_first_line(cell.source)
        sliders = read_sliders(cell.source)
        outputs = live.run_cell(cell.source, ns, {k: v[3] for k, v in sliders.items()})
        code = shown_code(cell.source)

        pieces = []
        if sliders:
            pieces.append(html_sliders(sliders, opts.get("rerun", ALL)))
        if opts.get("edit") and not sliders:  # a cell has sliders or an editor, not both
            # the editor holds all the code, since what's in it is what runs
            pieces.append(html_editor(live.clean(cell.source).strip(), opts.get("rerun", 0)))
        elif code and not opts.get("hide"):
            pieces.append(html_code(code, folded=opts.get("fold", False)))
        pieces.append(html_outputs(outputs))
        parts.append(f'<div class="cell" data-cell="{index}">{"".join(pieces)}</div>')
    close_sections(0)
    return title or "Potential flow", "\n".join(parts), cells


def main(dest="dist/index.html", notebook=NOTEBOOK):
    title, body, cells = build(nbformat.read(notebook, as_version=4))
    config = {  # read by page.js
        "pyodide": f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/",
        "plotly": plotly.__version__,
        "cells": cells,
        "live_py": (ROOT / "page" / "live.py").read_text(),
    }
    page = (ROOT / "page" / "template.html").read_text()
    page = (page.replace("{{title}}", html.escape(title))
                .replace("{{plotly_js}}", plotly.offline.get_plotlyjs_version())
                .replace("{{config}}", json.dumps(config).replace("</", "<\\/"))
                .replace("{{body}}", body))
    css = (ROOT / "page" / "style.css").read_text()
    css += HtmlFormatter(style="monokai").get_style_defs(".highlight")  # code colours, dark

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page)
    (dest.parent / "style.css").write_text(css)
    for name in ("page.js", "worker.js"):
        (dest.parent / name).write_text((ROOT / "page" / name).read_text())


if __name__ == "__main__":
    main(*sys.argv[1:3])
