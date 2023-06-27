"""
This module provides functionality for managing conda ops projects and configurations.

The main functions provided by this module are:
- proj_create: Initialize the conda ops project by creating a .conda-ops directory and config file.
- proj_load: Load the conda ops configuration file.
- proj_check: Check the existence and consistency of the project and config object.

In addition to project-level commands, the module also includes helper functions such as find_conda_ops_dir
and find_upwards, which are used for locating the conda ops configuration directory and searching for files/directories
recursively.

Please note that this module relies on other modules and packages within the project, such as .kvstore, ._paths,
.utils, and .kvstore. Make sure to install the necessary dependencies before using the functions in this module.
"""

from pathlib import Path
import sys

from .kvstore import KVStore
from ._paths import PathStore

from .utils import CONDA_OPS_DIR_NAME, CONFIG_FILENAME, logger


##################################################################
#
# Project Level Commands
#
##################################################################


def proj_create():
    """
    Initialize the conda ops project by creating a .conda-ops directory and config file.

    Return the config dict
    """
    conda_ops_path = Path.cwd() / CONDA_OPS_DIR_NAME

    if conda_ops_path.exists():
        logger.warning("conda ops has already been initialized")
        if input("Would you like to reinitialize (this will overwrite the existing config)? (y/n) ").lower() != "y":
            sys.exit(0)
        logger.error("Unimplemented: Reinitialize from the new templates as with git init with no overwriting")
    else:
        conda_ops_path.mkdir()

    logger.info("Initializing conda ops environment.")

    # setup initial config
    config_file = conda_ops_path / CONFIG_FILENAME

    # currently defaults to creating an env_name based on the location of the project
    env_name = Path.cwd().name

    _config_paths = {
        "ops_dir": "${catalog_path}",
        "requirements": "${ops_dir}/environment.yml",
        "lockfile": "${ops_dir}/lockfile.json",
        "explicit_lockfile": "${ops_dir}/lockfile.explicit",
        "pip_explicit_lockfile": "${ops_dir}/lockfile.pypi",
    }
    _config_settings = {
        "env_name": env_name,
    }

    config = {}

    config["settings"] = KVStore(_config_settings, config_file=config_file, config_section="OPS_SETTINGS")
    config["paths"] = PathStore(_config_paths, config_file=config_file, config_section="OPS_PATHS")

    return config


def proj_load(die_on_error=True):
    """Load the conda ops configuration file."""
    ops_dir = find_conda_ops_dir(die_on_error=die_on_error)

    if ops_dir is not None:
        logger.debug("Loading project config")
        path_config = PathStore(config_file=(ops_dir / CONFIG_FILENAME), config_section="OPS_PATHS")
        ops_config = KVStore(config_file=(ops_dir / CONFIG_FILENAME), config_section="OPS_SETTINGS")
        config = {"paths": path_config, "settings": ops_config}
    else:
        config = None
    return config


def proj_check(config=None, die_on_error=True):
    """
    Check the existence and consistency of the project and config object
    """
    check = True
    if config is None:
        config = proj_load(die_on_error=die_on_error)
    if config is None:
        check = False
        logger.error("No managed conda environment found.")
        logger.info("To place the current directory under conda ops management:")
        logger.info(">>> conda ops proj create")
        # logger.info(">>> conda ops init")
        logger.info("To change to a managed directory:")
        logger.info(">>> cd path/to/managed/conda/project")
    else:
        env_name = config["settings"].get("env_name", None)
        if env_name is None:
            check = False
            logger.error("Config is missing an environment name")
            logger.info("To reinitialize your conda ops project:")
            logger.info(">>> conda ops proj create")
            # logger.info(">>> conda ops init")
        paths = config["paths"]
        if len(paths) < 4:
            check = False
            logger.error("Config is missing paths")
            logger.info("To reinitialize your conda ops project:")
            logger.info(">>> conda ops proj create")
            # logger.info(">>> conda ops init")

    if die_on_error and not check:
        sys.exit(1)
    return check


############################################
#
# Helper Functions
#
############################################


def find_conda_ops_dir(die_on_error=True):
    """
    Locate the conda ops configuration directory.

    Searches current and all parent directories.

    die_on_error: Boolean
        if ops_dir is not found:
            if True, exit with error
            if False, return None
    """
    logger.debug("Searching for conda_ops dir.")
    ops_dir = find_upwards(Path.cwd(), CONDA_OPS_DIR_NAME)
    if ops_dir is None:
        message = "No managed conda environment found (here or in parent directories)."
        if die_on_error:
            logger.error(message)
        else:
            logger.warning(message)
        logger.info("To place the current directory under conda ops management:")
        logger.info(">>> conda ops proj create")
        # logger.info(">>> conda ops init")
        logger.info("To change to a managed directory:")
        logger.info(">>> cd path/to/managed/conda/project")

        if die_on_error:
            sys.exit(1)
    return ops_dir


def find_upwards(cwd, filename):
    """
    Search recursively for a file/directory.

    Start searching in current directory, then upwards through all parents,
    stopping at the root directory.

    Arguments:
    ---------
    cwd :: string, current working directory
    filename :: string, the filename or directory to look for.

    Returns
    -------
    pathlib.Path, the location of the first file found or
    None, if none was found
    """
    if cwd == cwd.parent or cwd == Path(cwd.root):
        return None

    fullpath = cwd / filename

    try:
        return fullpath if fullpath.exists() else find_upwards(cwd.parent, filename)
    except RecursionError:
        return None
