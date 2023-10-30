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

import json
from pathlib import Path
import os
import sys
import traceback

from .kvstore import KVStore
from ._paths import PathStore

from .utils import CONDA_OPS_DIR_NAME, CONFIG_FILENAME, logger
from .python_api import run_command


##################################################################
#
# Project Level Commands
#
##################################################################

# files to be created at initialization
INITIAL_FILE_PATHS = {
    "condarc": "${ops_dir}/.condarc",
    "gitignore": "${ops_dir}/.gitignore",
    "requirements": "${project_dir}/environment.yml",
}
# other paths to include
OTHER_CONFIG_PATHS = {
    "ops_dir": "${catalog_path}",
    "project_dir": "${ops_dir}/..",
    "explicit_lockfile": "${ops_dir}/lockfile.explicit",
    "lockfile": "${ops_dir}/lockfile.json",
    "lockfile_url_lookup": "${ops_dir}/lockfile-local-url.ini",
    "nohash_explicit_lockfile": "${ops_dir}/lockfile.nohash",
    "pip_explicit_lockfile": "${ops_dir}/lockfile.pypi",
    "env_dir": "${ops_dir}/envs",
}


def proj_create(prefix="", input_value=None):
    """
    Initialize the conda ops project by creating a .conda-ops directory and config file.

    Return the config dict.

    Note: This does **not** create the .condarc configuration file or the requirements file.
    """
    conda_ops_path = Path.cwd() / CONDA_OPS_DIR_NAME

    if conda_ops_path.exists():
        logger.warning("conda ops has already been initialized")
        if input_value is None:
            overwrite_value = input("Would you like to reinitialize (this will overwrite the existing conda-ops basic setup)? (y/n) ").lower()
        else:
            overwrite_value = input_value
        if overwrite_value != "y":
            return proj_load(), False
        else:
            overwrite = True
    else:
        conda_ops_path.mkdir()
        overwrite = False

    if overwrite:
        logger.info("Re-initializing conda ops project")
    else:
        logger.info("Initializing conda ops project.")

    # setup initial config
    config_file = conda_ops_path / CONFIG_FILENAME

    if overwrite and config_file.exists():
        config_file.unlink()

    # currently defaults to creating an env_name based on the location of the project
    env_name = Path.cwd().name.lower()

    _config_paths = {**INITIAL_FILE_PATHS, **OTHER_CONFIG_PATHS}
    _config_settings = {"env_name": env_name, "prefix": prefix}

    # create config_file
    KVStore(_config_settings, config_file=config_file, config_section="OPS_SETTINGS")
    PathStore(_config_paths, config_file=config_file, config_section="OPS_PATHS")

    # and load its contents
    config = {}
    config["env_settings"] = KVStore(config_file=config_file, config_section="OPS_SETTINGS")
    config["paths"] = PathStore(config_file=config_file, config_section="OPS_PATHS")

    # create lockfile_url_lookup
    lockfile_lookup_file = config["paths"]["lockfile_url_lookup"]
    if lockfile_lookup_file.exists() and overwrite:
        if input_value is None:
            lookup_overwrite_value = input("Would you like to clear all local url lookup information? (y/n) ").lower()
        else:
            lookup_overwrite_value = input_value
        if lookup_overwrite_value != "y":
            lookup_dict = KVStore(config_file=config["paths"]["lockfile_url_lookup"], config_section="LOCKFILE_URLS")
        else:
            lookup_dict = {}
        lockfile_lookup_file.unlink()
    else:
        lookup_dict = {}

    KVStore(lookup_dict, config_file=config["paths"]["lockfile_url_lookup"], config_section="LOCKFILE_URLS")

    # create .gitignore entry
    lockfile_url_entry = "*" + config["paths"]["lockfile_url_lookup"].name + "*"
    gitignore_path = config["paths"]["gitignore"]

    if gitignore_path.exists():
        with open(gitignore_path, "r") as filehandle:
            gitignore_content = filehandle.read()
    else:
        s = "\n"
        gitignore_content = f"{s.join(['*.explicit', '*.nohash', '*.pypi', '.ops.*', 'envs'])}"

    if lockfile_url_entry not in gitignore_content:
        gitignore_content += "\n" + lockfile_url_entry
        with open(gitignore_path, "w") as filehandle:
            filehandle.write(gitignore_content)

    return config, overwrite


def proj_load(die_on_error=True):
    """Load the conda ops configuration file."""
    ops_dir = find_conda_ops_dir(die_on_error=die_on_error)

    if ops_dir is not None:
        logger.debug("Loading project config")
        path_config = PathStore(config_file=(ops_dir / CONFIG_FILENAME), config_section="OPS_PATHS")
        ops_config = KVStore(config_file=(ops_dir / CONFIG_FILENAME), config_section="OPS_SETTINGS")
        config = {"paths": path_config, "env_settings": ops_config}
    else:
        config = None
    return config


def proj_check(config=None, die_on_error=True, required_keys=None):
    """
    Check the existence and consistency of the project and config object.

    Args:
        config (dict, optional): Configuration object. If not provided,
            it will be loaded using `proj_load`.
        die_on_error (bool, optional): Flag indicating whether to exit the program if error occurs.
        required_keys (list, optional): List of required keys in the config object.
            Default is a predefined list of all known keys.

    Returns:
        bool: True if the project and config object are valid and consistent, False otherwise.
    """
    if required_keys is None:
        config_paths = {**INITIAL_FILE_PATHS, **OTHER_CONFIG_PATHS}
        required_keys = list(config_paths.keys())

    check = True
    if config is None:
        config = proj_load(die_on_error=die_on_error)
    if config is None:
        check = False
        logger.error("No managed conda environment found.")
        logger.info("To place the current directory under conda ops management:")
        logger.info(">>> conda ops init")
        logger.info("To change to a managed directory:")
        logger.info(">>> cd path/to/managed/conda/project")
    else:
        try:
            env_name = config["env_settings"].get("env_name", None)
            prefix = config["env_settings"].get("prefix", None)
        except Exception as e:
            env_name = None
            prefix = None
        if env_name is None and prefix is None:
            check = False
            logger.error("Config is missing an environment name and prefix. It must have at least one.")
            logger.info("To reinitialize your conda ops project:")
            logger.info(">>> conda ops init")
        if check:
            paths = list(config["paths"].keys())
            for key in required_keys:
                if key not in paths:
                    check = False
                    logger.error(f"The configuration file is missing a mandatory key: {key}")
                    logger.info("To reinitialize your conda ops project:")
                    logger.info(">>> conda ops init")
        if check:
            # only do this one if the keys exist
            missing_files = []
            for key in INITIAL_FILE_PATHS.keys():
                path = config["paths"].get(key)
                if not path.exists():
                    check = False
                    missing_files.append(key)
            if len(missing_files) > 0:
                logger.warning("The following configuration files are missing:")
                ws = "\n   "
                logger.info(f"   {ws.join(missing_files)}")
                logger.info("To reinitialize your conda ops project:")
                logger.info(">>> conda ops init")

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
        logger.info(">>> conda ops init")
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
