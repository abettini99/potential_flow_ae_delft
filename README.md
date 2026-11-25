# AE2130-I - Potential Flow Tool

This tool is developed to visualize potential flows in an intuitive interface for second-year bachelor-level students. It is developed for the introductory aerodynamics course AE2130-I at Delft University of Technology.

## Open the notebook

[Open the interactive notebook](https://abettini99.github.io/potential_flow_ae_delft/notebooks/index.html?path=potential_flow.ipynb) — it runs entirely in the browser (JupyterLite), so students need nothing installed.

## How it is built

Every push to `main` runs `.github/workflows/deploy.yml`, which builds a JupyterLite site from the `content/` folder and deploys it to GitHub Pages. Edit `content/potential_flow.ipynb` and push; the site updates in a few minutes.
