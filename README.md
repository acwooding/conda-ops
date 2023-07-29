# conda-ops

## Installation
Requires modern conda with plugin support (and likely python/pip). e.g.

```
>>> conda install -n base -c defaults conda==23.5.0
>>> conda install -n base -c defaults python=3.11
```

To install the plugin locally, run `pip install -e .` from your base `conda` install. (If you install it into a conda environment, you will have to use that environment's `conda` installation to pick up the plugin, so installing conda into that envrionment and running `path/to/environment/conda/bin ops` instead of `conda ops`).

To uninstall, `pip uninstall conda-ops`.

## Basic Usage

The interface for conda ops is still experimental and may change between commits. The best way to see what can be done at a given moment is to use the help menu:
```
conda ops --help
```
or to check the status of your conda ops project via
```
conda ops
```
and follow the prompts from there.


## Testing and Linting
To set up testing or linting, you'll need the depedencies specified under `[project.optional-dependencies]` in the `pyproject.toml` installed into your environment.

### Running tests
Once dependencies are set up, run `pytest` or `coverage run -m pytest`. After running `coverage`, `coverage report` will display the basic coverage information and `coverage html` will generate an html interactive coverage report.

### Linting
For now, keep a line length of 200

Always run black for auto-formatting.
* `black . -l 200`: specify a larger max line length with black

Take a look at flake8 or pylint reports for linting. flake8 is a more lightweight.
* `flake8 --max-line-length=200 --exclude conda_ops_later.py`
* `pylint src --max-line-length=200 --ignore=conda_ops_later.py`