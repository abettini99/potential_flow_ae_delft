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
- Sliders over plain code: make the first line of a cell a comment like
  ```python
  # @interact(Vinf=(0.5, 5.0, 0.1), angle=(-30, 30, 1), Lambda=(1, 5, 0.1))
  phi_1, psi_1 = uniform(Vinf, np.deg2rad(angle))
  ...
  ```
  `(min, max, step)` gives a slider, a list a dropdown, `True`/`False` a checkbox. On the page the sliders appear above the code; moving one sets those variables, reruns this cell and every code cell below (`rerun=2` after the closing parenthesis limits it to the next 2). Each slider starts at the variable's value from an earlier cell (e.g. `Vinf, angle, Lambda = 1, 30, 1`), so define them before this cell; the cell then also runs unchanged in Colab or Jupyter, where the comment is ignored.
- Sliders for parameters: write each parameter on its own line with Colab's form syntax, for example
  ```python
  Vinf = 1.0    # @param {type:"slider", min:0.5, max:5, step:0.1}
  angle = 30    # @param {type:"slider", min:-90, max:90, step:1}
  show_vectors = True  # @param {type:"boolean"}
  shape = "cylinder"   # @param ["cylinder", "oval"]
  ```
  It is plain Python (Colab even shows the same sliders). On the page the cell shows only the controls; moving one sets the variable and reruns every code cell below. Add `# page: rerun=2` as the first line to rerun only the next 2. `{type:"number"}` gives a number box.
- Notebook tags still work: `remove-cell` hides a cell completely (code and output), `remove-input` is the same as `# page:hide`. Colab's ⋮ > Form > Hide code also counts as hide.
- Packages: anything Pyodide ships (numpy, scipy, ...) loads automatically from the imports; plotly is installed on the fly.

Preview locally with `pip install -r requirements.txt && python build_page.py dist/index.html`, then open `dist/index.html` through a local web server (`python -m http.server -d dist`).
