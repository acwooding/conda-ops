# conda-ops
Creating, maintaining and not breaking conda-based python environments can be messy and complicated. Sharing environments (or creating environments to run a notebook or project that's been handed to you) is even harder. `conda-ops` provides a simple, easy-to-use solution to the often confusing, complex, and complicated python+conda packaging and environment nightmare that "just works". Think of it like "poetry for conda". It helps keep track of and integrate pip installed packages with conda, which is [notoriously fraught with peril](https://www.anaconda.com/blog/using-pip-in-a-conda-environment) but impossible to avoid in an everyday development environment (`pip install -e .`).

`conda ops` is a command line tool, in fact, a conda plugin, that manages your project's conda environment and transparently keeps track of:

* what you asked for (requirements file)
* what you needed (lock file)
* your shareable conda settings (project-based .condarc file)

It gives you the ability to run status checks on your environment and lets you know what you should or can do next (`conda ops`) to keep everything working and in sync.

## Installation

Requirements: Note that `conda-ops` requires modern conda with plugin support (and python/pip). e.g.

```
>>> conda install -n base -c defaults conda>=23.5.0
>>> conda install -n base -c defaults python>=3.11
```

`conda-ops` is still under significant development and is changing rapidly. We recommend updating it regularly no matter which version you choose to install.

For the latest development version:

`conda run -n base pip install git+https://github.com/acwooding/conda-ops`

For the latest alpha release available via PyPI:

`conda run -n base pip install conda-ops`


To install the plugin locally in development mode, clone the repo and then run `pip install -e .` from your base `conda` install (e.g. `conda run -n base pip install -e .`.

Please make sure that you install `conda-ops` into your `base` conda environment for the plugin for work properly. (If you install it into a conda environment, you will have to use that environment's `conda` installation to pick up the plugin; that is, installing conda into that environment and running `path/to/environment/conda/bin ops` instead of `conda ops`).

To uninstall, `pip uninstall conda-ops` from your within your `base` conda environment.

## Basic Usage

To set up a conda ops managed project environment in the current working directory (similar to `git init`):
```
conda ops init
```
This creates a `.conda-ops` directory that contains the conda ops configuration files and lock files, and an `environment.yml` file if it doesn't already exist.

Similar to `git` you can always check the status of your conda ops managed environment via `conda ops status` or simply, `conda ops`. This will prompt you for what you may need to next do if anything ever gets out of sync.

Beyond `conda ops init` and `conda ops`, there are only 3 commands that you need to regularly:
* `conda ops add`: Add packages to the requirements file.
* `conda ops remove`: Remove packages from the requirements file. Removes all versions of the packages from any channel they are found in.
* `conda ops sync`: Sync the environment and lock file with the requirements file.

To add packages from conda channels other than the default conda channel, you can use `-c` or `--channel`:
```
conda ops add my-package-1 my-package-2 -c my-other-channel
```
For anything using `pip` instead of `conda`, we treat `pip` as special conda channel:
```
conda ops add my-local-package -c pip
```
We also support VCS and editable installs via pip. For example, the ubiquitous `pip install -e .` can be done as:
```
conda ops add "-e ." -c pip
conda ops sync
```
or simply
```
conda ops install "-e ." -c pip
```

As a convenience `conda ops install` works like `conda install` but allows conda ops to track the installed packages transparently and reproducibly (effectively, it does a `conda ops add` and then `conda ops sync`). Similarly, `conda ops uninstall` works like `conda uninstall` and effectively consists of `conda ops remove` and `conda ops sync`.

Other helpful commands include:
* `conda ops reqs list`: Show the contents of the requirements file.
* `conda ops reqs edit`: Open the requirements file in the default editor.
* `conda ops config`: Behaves similarly to `conda config` but only handles the configuration tracked in `.conda-ops/.condarc`. See `conda ops config --help` for details.

The full list of commands can be accessed via the help menu: `conda ops --help`.

There is also a project specific `.condarc` file that is always and only invoked by `conda ops` within the current conda ops project. This configuration file contains all of the conda config settings relating to the solver and the channel settings so that solves are reproducible and the relevant configurations are easily shareable. See `conda ops config --help` for more details on how to work with and manage the conda configuration within a conda ops project. Note: we often find ourselves using `conda ops config --set solver libmamba`.

The interface for conda ops is still experimental and may change between commits. The best way to see what can be done at a given moment is to use the help menu:
```
conda ops --help
```
or to check the status of your conda ops project via
```
conda ops
```
and follow the prompts from there.


## Development Requirements: Testing and Linting
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