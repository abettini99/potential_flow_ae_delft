# AE2130-I - Potential Flow Tool

This tool is developed to visualize potential flows in an intuitive interface for second-year bachelor-level students. It is developed for the introductory aerodynamics course AE2130-I at Delft University of Technology.

## The site

- **https://abettini99.github.io/potential_flow_ae_delft/** is the notebook shown as a web page: text, maths, code and plots, in the homepage's style.
- **Open as notebook** on that page opens the same notebook in JupyterLite, where anyone can change and run all of it.

Every push to `main` rebuilds both from `content/potential_flow.ipynb` (`.github/workflows/deploy.yml`, about a minute).

## Writing the notebook

Make plots with Plotly (`fig.show()`, or a figure on a cell's last line). Printed text shows too.

Code is shown on the page by default. The first line of a code cell can change that:

| First line | On the page |
|---|---|
| *(nothing special)* | code, then its output |
| `# page:hide` | output only |
| `# page:fold` | code folded behind a "Code" toggle |
| `# page:edit` | code in an editor with a Run button (or Shift+Enter) |
| `# page:edit rerun=2` | same, and Run also reruns the next 2 code cells (`rerun=all`: every cell below) |

**Hiding part of a cell.** Lines between `# page:hide-from` and `# page:hide-to` are left off the page but still run. Without a `# page:hide-to`, it hides to the end of the cell. (Editable cells always show all their code.)

**Sliders.** Put `# page:slider (min, max, step)` above a `name = value` line, anywhere in a cell. The value is where the slider starts. Moving a slider puts its value in that line and reruns the cell and every cell below it; `# page:rerun=2` on the cell's first line reruns only the next 2.

```python
# page:rerun=2

# page:slider (0.5, 5.0, 0.1)
Vinf = 1

# page:slider (-30, 30, 1)
angle = 0
```

A cell has sliders or an editor, not both. All of these are comments, so the notebook runs unchanged in Colab or Jupyter.

## How it works

Three small files in this repo, plus the workflow:

- `build_page.py` reads the notebook, runs every code cell in order, and writes `index.html` with the text, highlighted code and plots already in it. The first-line markers above are read here.
- `page/live.py` runs one cell and collects what it printed and the Plotly figures it made. The build uses it, and so does the page.
- `page/page.js` draws the plots, then loads Python in the browser ([Pyodide](https://pyodide.org)) and runs the cells again so that sliders and Run buttons can rerun code. Until that has loaded, sliders and editors show "Loading Python".
- `page/template.html` and `page/style.css` are the page's frame and look (copied from the homepage).

To preview locally: `pip install -r requirements.txt && python build_page.py dist/index.html && python -m http.server -d dist`, then open http://localhost:8000.
