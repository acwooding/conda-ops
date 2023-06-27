import json
import logging
import sys
from pathlib import Path

from ruamel.yaml import YAML

from .python_api import run_command

yaml = YAML()
yaml.default_flow_style = False
yaml.width = 4096
yaml.indent(offset=4)


logger = logging.getLogger()

conda_logger = logging.getLogger("conda.cli.python_api")
conda_logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s %(name)-15s %(levelname)-8s %(processName)-10s %(message)s"))
conda_logger.addHandler(ch)

sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter(" %(levelname)-8s (%(name)s) %(message)s"))
logger.addHandler(sh)

CONDA_OPS_DIR_NAME = ".conda-ops"
CONFIG_FILENAME = "config.ini"


def get_conda_info():
    """Get conda configuration information.

    This currently peeks into the conda internals.
    XXX Should this maybe be a conda info API call instead?
    XXX previous get_info_dict, but this does not contain the envs
    """
    stdout, stderr, result_code = run_command("info", "--json", use_exception_handler=True)
    if result_code != 0:
        logger.info(stdout)
        logger.info(stderr)
        sys.exit(result_code)
    return json.loads(stdout)


def check_env_exists(env_name):
    """
    Given the name of a conda environment, check if it exists
    """
    json_output = get_conda_info()

    env_list = [Path(x).name for x in json_output["envs"]]
    return env_name in env_list


def check_env_active(env_name):
    """
    Given the name of a conda environment, check if it is active
    """
    conda_info = get_conda_info()
    active_env = conda_info["active_prefix_name"]

    return active_env == env_name
