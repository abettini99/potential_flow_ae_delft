# AE2130-I - Potential Flow Tool

This tool is developed to visualize potential flows in an intuitive interface for second-year bachelor-level students. It is developed for the introductory aerodynamics course AE2130-I at Delft University of Technology.

## The site

- **https://abettini99.github.io/potential_flow_ae_delft/** is the notebook rendered as a normal web page: text, maths, plots and sliders, in the homepage's style. Plots show immediately; Python then loads in the background (a spinner shows next to each set of sliders) and the sliders rerun the notebook's own functions.
- **Open as notebook** on that page opens the same notebook in JupyterLite, where students can edit and run the code.

Both are built from `content/potential_flow.ipynb` by `.github/workflows/deploy.yml` on every push to `main`.

## Writing the notebook so the page works

- Interactive parts: use `ipywidgets.interact` (or `@interact`) with `FloatSlider`, `IntSlider`, `Dropdown`, `Checkbox` or the `(min, max, step)` shorthand, and have the function `return` a Plotly figure or call `fig.show()`. The same code works in JupyterLite and on the page.
- Plots: use Plotly (`plotly.graph_objects`). Matplotlib output is not carried over to the page.
- Code is shown on the page by default. Put one of these on a cell's first line to change that:
  - `# page:hide`: the cell runs but its code isn't shown (its output and sliders still are).
  - `# page:fold`: the code is folded behind a "Code" toggle.
  - `# page:edit rerun=2`: as below, and Run also reruns the next 2 code cells (hidden ones count) so their plots and sliders update. `rerun=all` reruns every code cell below. Use it when later cells depend on values set in the editable cell.
  - `# page:edit`: readers can edit the code and press Run (or Shift+Enter) on the page itself. It runs in the same Python session as the rest of the page, so it can use everything defined above it, and a redefined function is picked up by sliders that look it up by name.
- Notebook tags still work: `remove-cell` hides a cell completely (code and output), `remove-input` is the same as `# page:hide`. Colab's ⋮ > Form > Hide code also counts as hide.
- Packages: anything Pyodide ships (numpy, scipy, ...) loads automatically from the imports; plotly is installed on the fly.

Preview locally with `pip install -r requirements.txt && python build_page.py dist/index.html`, then open `dist/index.html` through a local web server (`python -m http.server -d dist`).
