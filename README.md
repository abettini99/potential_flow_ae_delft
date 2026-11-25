# AE2130-I - Potential Flow Tool

This tool is developed to visualize potential flows in an intuitive interface for second-year bachelor-level students. It is developed for the introductory aerodynamics course AE2130-I at Delft University of Technology.

## The site

- **https://abettini99.github.io/potential_flow_ae_delft/** is the notebook rendered as a normal web page: text, maths, plots and sliders, in the homepage's style. Plots show immediately; Python then loads in the background (a spinner shows next to each set of sliders) and the sliders rerun the notebook's own functions.
- **Open as notebook** on that page opens the same notebook in JupyterLite, where students can edit and run the code.

Both are built from `content/potential_flow.ipynb` by `.github/workflows/deploy.yml` on every push to `main`.

## Writing the notebook so the page works

- Interactive parts: use `ipywidgets.interact` (or `@interact`) with `FloatSlider`, `IntSlider`, `Dropdown`, `Checkbox` or the `(min, max, step)` shorthand, and have the function `return` a Plotly figure or call `fig.show()`. The same code works in JupyterLite and on the page.
- Plots: use Plotly (`plotly.graph_objects`). Matplotlib output is not carried over to the page.
- Hiding code: on the page, code is folded behind "Show code". To hide a cell's code completely, make `# page:hide` its first line (or use Colab's ⋮ > Form > Hide code, or tag it `remove-input`). The cell still runs; a hidden cell without output disappears from the page.
- Cell tags (View > Cell toolbar > Tags in Jupyter): `remove-cell` runs a cell without showing it (setup, imports), `remove-input` shows only the output, `show-input` shows the code unfolded. Code is folded behind "Show code" by default.
- Packages: anything Pyodide ships (numpy, scipy, ...) loads automatically from the imports; plotly is installed on the fly.

Preview locally with `pip install -r requirements.txt && python build_page.py dist/index.html`, then open `dist/index.html` through a local web server (`python -m http.server -d dist`).
