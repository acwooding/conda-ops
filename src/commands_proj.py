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

from contextlib import AbstractContextManager
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


def proj_create():
    """
    Initialize the conda ops project by creating a .conda-ops directory and config file.

    Return the config dict.

    Note: This does **not** create the .condarc configuration file or the requirements file.
    """
    conda_ops_path = Path.cwd() / CONDA_OPS_DIR_NAME

    if conda_ops_path.exists():
        logger.warning("conda ops has already been initialized")
        if input("Would you like to reinitialize (this will overwrite the existing conda-ops basic setup)? (y/n) ").lower() != "y":
            return proj_load()
    else:
        conda_ops_path.mkdir()

    logger.info("Initializing conda ops environment.")

    # setup initial config
    config_file = conda_ops_path / CONFIG_FILENAME

    # currently defaults to creating an env_name based on the location of the project
    env_name = Path.cwd().name.lower()

    _config_paths = {
        "ops_dir": "${catalog_path}",
        "project_dir": "${ops_dir}/..",
        "requirements": "${project_dir}/environment.yml",
        "lockfile": "${ops_dir}/lockfile.json",
        "explicit_lockfile": "${ops_dir}/lockfile.explicit",
        "pip_explicit_lockfile": "${ops_dir}/lockfile.pypi",
        "nohash_explicit_lockfile": "${ops_dir}/lockfile.nohash",
        "condarc": "${ops_dir}/.condarc",
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
        required_keys = [
            "ops_dir",
            "requirements",
            "lockfile",
            "explicit_lockfile",
            "pip_explicit_lockfile",
            "condarc",
        ]
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
        env_name = config["settings"].get("env_name", None)
        if env_name is None:
            check = False
            logger.error("Config is missing an environment name")
            logger.info("To reinitialize your conda ops project:")
            logger.info(">>> conda ops init")
        paths = list(config["paths"].keys())
        for key in required_keys:
            if key not in paths:
                logger.error(f"config.ini missing mandatory key: {key}")
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


def get_conda_info():
    """Get conda configuration information.

    XXX Should this maybe look into the conda internals instead?
    XXX previous get_info_dict did this, but the internal call does not contain the envs
    """
    # Note: we do not want or need to use the condarc context handler here.
    stdout, stderr, result_code = run_command("info", "--json", use_exception_handler=False)
    if result_code != 0:
        logger.info(stdout)
        logger.info(stderr)
        sys.exit(result_code)
    return json.loads(stdout)


class CondaOpsManagedCondarc(AbstractContextManager):
    """
    Wrapper for calls to conda that set and unset the CONDARC value to the rc_path value.

    Since conda-ops track config settings that matter for the solver (solver and channel configuartion)
    including pip_interop_enabled, we use the context handler for the following conda commands:
    * conda create
    * conda install
    * conda list (it gives us conda and pip packages)
    * conda remove/uninstall (except remove --all)
    * conda run pip <any pip command>
    """

    def __init__(self, rc_path):
        self.rc_path = str(rc_path)

    def __enter__(self):
        self.old_condarc = os.environ.get("CONDARC")
        if Path(self.rc_path).exists():
            os.environ["CONDARC"] = self.rc_path
        else:
            logger.error("Conda ops managed .condarc file does not exist")
            logger.info("To create the managed .condarc file:")
            logger.info(">>> conda ops config create")
            sys.exit(1)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.old_condarc is not None:
            os.environ["CONDARC"] = self.old_condarc
        else:
            del os.environ["CONDARC"]
        if exc_type is SystemExit:
            logger.error("System Exiting...")
            logger.debug(f"exc_value: {exc_value} \n")
            logger.debug(f"exc_traceback: {traceback.print_tb(exc_traceback)}")
