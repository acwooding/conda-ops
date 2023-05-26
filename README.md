# conda-ops

Requires modern conda with plugin support (and likely python/pip). e.g.

```
>>> conda install -n base -c defaults conda==23.5.0
>>> conda install -n base -c defaults python=3.11
```

To install the plugin locally, run `pip install -e .` from your base `conda` install. (If you install it into a conda environment, you will have to use that environment's `conda` installation to pick up the plugin, so installing conda into that envrionment and running `path/to/environment/conda/bin ops` instead of `conda ops`).

To uninstall, `pip uninstall conda-ops`
