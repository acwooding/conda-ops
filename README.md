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

### Initialization
To set up a conda ops managed project environment in the current working directory (similar to `git init`):
```
conda ops init
```
This creates a `.conda-ops` directory that contains the conda ops configuration files and lock files, and an `environment.yml` file if it doesn't already exist.

Similar to `git` you can always check the status of your conda ops managed environment via `conda ops status` or simply, `conda ops`. This will prompt you for what you may need to next do if anything ever gets out of sync.

### Package Management
Beyond `conda ops init` and `conda ops`, there are only 3 commands that you need to regularly:
* `conda ops add`: Add packages to the requirements file.
* `conda ops remove`: Remove packages from the requirements file. Removes all versions of the packages from any channel they are found in.
* `conda ops sync`: Sync the environment and lock file with the requirements file.

To add packages from conda channels other than the default conda channel, you can use `-c` or `--channel`:
```
conda ops add -c channel1 package1 package2 -c channel2 package3
```
This adds the entries `channel1::package1`, `channel1::package2` and `channel2::package3` to the requirements file and is shorthand for
```
conda ops add channel1::package1 channel1::package2 channel2::package3
```

For anything using `pip` instead of `conda`, you can use `--pip` or `-e` depending on the circumstance:
```
conda ops add --pip package1
```
will add `package1` under the `pip` section of the requirements file.

We also support VCS and editable installs via pip. For example, the ubiquitous `pip install -e .` can be done as:
```
conda ops add -e .
conda ops sync
```
or simply
```
conda ops install -e .
```
In this case, the line `-e .` is added to the pip section of the requirements file. If `-e` is used, `--pip` is not needed as editable installs are done via pip.

As a convenience `conda ops install` works like `conda install` but allows conda ops to track the installed packages transparently and reproducibly (it does a `conda ops add` and then `conda ops sync`). Similarly, `conda ops uninstall` works like `conda uninstall` and consists of `conda ops remove` and `conda ops sync`. (Note that because `install` is an `add`+`sync` local pacakges specified for pip installation are relative to the requirements file).

### Helpful Commands
Other helpful commands include:
* `conda ops reqs list`: Show the contents of the requirements file.
* `conda ops reqs edit`: Open the requirements file in the default editor.
* `conda ops config`: Behaves similarly to `conda config` but only handles the configuration tracked in `.conda-ops/.condarc`. See `conda ops config --help` for details.
* `conda ops env clean`: Remove any temporary environments that have been left lying around.

The interface for conda ops is still experimental and may change between commits. The best way to see what can be done at a given moment is to use the help menu:
```
conda ops --help
```
or to check the status of your conda ops project via
```
conda ops
```
and follow the prompts from there.

### Working with Jupyter
If you want to work with your conda-ops project environment from with a Jupyter Notebook or Jupyter Lab context, we recommend running your Jupyter instance from a **different** environment from your current project environment, and making sure that the (conda) environment you're running Jupyter from has `nb_conda_kernels` installed in it so that you can select your conda-ops project environment from within the list of kernels in Jupyter (e.g. have a separate conda-ops project for managing your Jupyter instance!)

To interact with and update your conda-ops managed project environment, we recommend using a terminal where the managed project environment is **not** active. You may need to add a cell at the top of your notebooks with
```
%load_ext autoreload
%autoreload 2
```
so that changes to the environment automatically translate to the notebook. Everything should **just work**. If not, file an issue and we'll help to sort it out.

### Managing conda Configurations
There is also a project specific `.condarc` file that is always and only invoked by `conda ops` within the current conda ops project. This configuration file contains all of the conda config settings relating to the solver and the channel settings so that solves are reproducible and the relevant configurations are easily shareable. See `conda ops config --help` for more details on how to work with and manage the conda configuration within a conda ops project.

We get that things can sometimes be slow. If you'd like to try the libmamba to try to speed things up:
```
conda install -n base conda-libmamba-solver
conda ops config --set solver libmamba
```
Libmamba is especially useful if your environment isn't solving since it gives much better error messages (and quickly) about what's going on.

### Requirements File
`conda-ops` uses an `environment.yml` file as its requirements file. If you have an existing `environment.yml` file in your repo when you initialize a conda ops project (`conda ops init`), it will automatically pick up the existing file and use it. Furthermore, if there are any additions or changes that need to be made to make it compatible with `conda-ops` (namely, channels, if used, must all be specified in the section `channels` in order of preference), you will be prompted to have the file updated accordingly.

## Development Requirements: Testing and Linting
To set up testing or linting, you'll need the depedencies specified under `[project.optional-dependencies]` in the `pyproject.toml` installed into your environment.

### Running tests
Once dependencies are set up, run `pytest` or `coverage run -m pytest`. After running `coverage`, `coverage report` will display the basic coverage information and `coverage html` will generate an html interactive coverage report.

### Linting
For now, keep a line length of 200

Always run black for auto-formatting.
* `black . -l 200`: specify a larger max line length with black

Take a look at flake8 or pylint reports for linting. flake8 is more lightweight.
* `flake8 --max-line-length=200 --exclude conda_ops_later.py`
* `pylint src --max-line-length=200 --ignore=conda_ops_later.py`