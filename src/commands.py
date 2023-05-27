## Main Functionality

from pathlib import Path
import sys
import configparser
import json
from ruamel.yaml import YAML
from .split_requirements import create_split_files
from .python_api import run_command
import conda.cli.python_api

import logging

logger = logging.getLogger()

conda_logger = logging.getLogger("conda.cli.python_api")
conda_logger.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s %(name)-15s %(levelname)-8s %(processName)-10s %(message)s"))
conda_logger.addHandler(ch)

sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter(" %(levelname)-8s (%(name)s) %(message)s"))
logger.addHandler(sh)

CONDA_OPS_DIR_NAME = '.conda-ops'
STATUS_FILENAME = 'status.txt'
CONFIG_FILENAME = 'config.ini'
REQUIREMENTS_FILENAME = 'environment.yml'
LOCK_FILENAME = 'lockfile.json'
EXPLICIT_LOCK_FILENAME = 'lockfile.explicit'

yaml = YAML()
yaml.default_flow_style=False
yaml.width=4096
yaml.indent(offset=4)

def ops_init():
    '''
    Initialize the conda ops project by creating a .conda-ops directory including the conda-ops project structure
    '''

    conda_ops_path = Path.cwd() / CONDA_OPS_DIR_NAME

    if conda_ops_path.exists():
        logger.warning("conda ops has already been initialized")
        if input("Would you like to reinitialize (this will overwrite the existing config)? (y/n) ").lower() != 'y':
            sys.exit(0)
        logger.error("Unimplemented: Reinitialize from the new templates as with git init with no overwriting")
    else:
        conda_ops_path.mkdir()

    logger.info('Initializing conda ops environment.')

    # setup initial config
    config_file = conda_ops_path / CONFIG_FILENAME
    config = configparser.ConfigParser()

    # currently defaults to creating an env_name based on the location of the project
    env_name = Path.cwd().name
    config['DEFAULT'] = {'ENV_NAME': env_name}
    with open(config_file, 'w') as f:
        config.write(f)

    # create basic requirements file
    requirements_file = conda_ops_path / REQUIREMENTS_FILENAME
    if not requirements_file.exists():
        requirements_dict = {'name': env_name,
                             'channels': ['defaults'],
                             'channel-order': ['defaults'],
                             'dependencies': ['python', 'pip']}
        logger.info('rewriting')
        with open(requirements_file, 'w') as f:
            yaml.dump(requirements_dict, f)
    else:
        logger.info(f'Requirements file {requirements_file} already exists')
    logger.info(f'Initialized conda-ops project in {conda_ops_path.resolve()}')

def ops_create():
    '''
    Create the first lockfile and environment
    '''
    logger.info('TODO: check if the environment already exists...')

    ops_dir = find_conda_ops_dir()
    requirements_file = ops_dir / REQUIREMENTS_FILENAME

    requirements = yaml.load(requirements_file)
    env_name = requirements['name']

    logger.info('generating multi-step requirements files')
    create_split_files(requirements_file, ops_dir)

    with open(ops_dir / '.ops.channel-order.include', 'r') as f:
        order_list = f.read().split()

    logger.info('generating the lock file')
    # creating the environment with the first stage
    with open(ops_dir / f'.ops.{order_list[0]}-environment.txt') as f:
        package_list = f.read().split()

    create_args = ["-n", env_name] + package_list + ['--dry-run', '--json']

    stdout, stderr, result_code = run_command("create", create_args, use_exception_handler=True)
    if result_code != 0:
        logger.info(stdout)
        logger.info(stderr)
        sys.exit()
    json_reqs = json.loads(stdout)

    lock_file = ops_dir / LOCK_FILENAME
    with open(lock_file, 'w') as f:
        json.dump(json_reqs['actions'], f)

    logger.info('creating explicit file for installation')
    explicit_str = "# This file may be used to create an environment using:\n# $ conda create --name <env> --file <this file>\n@EXPLICIT\n"
    explicit_str += json_to_explicit(json_reqs['actions']['LINK'])

    explicit_lock_file = ops_dir / EXPLICIT_LOCK_FILENAME
    with open(explicit_lock_file, 'w') as f:
        f.write(explicit_str)

    logger.info(f"Creating the environment {env_name}")
    create_args = ["-n", env_name, "--file", str(explicit_lock_file)]
    stdout, stderr, result_code = run_command("create", create_args, use_exception_handler=True)
    logger.info(stdout)

    if len(order_list) > 1:
        ## XXX implement the next steps here
        logger.info(f"TODO: Implement multi-stage install here...currently ignorning channels other than {order_list[0]}")

    ## XXX Implement the pip step here
    logger.info('TODO: Implement the pip installation step here')

    status_file = ops_dir / STATUS_FILENAME
    with open(status_file, 'w') as f:
        f.write(f"Environment {env_name} created.")
    logger.info(f'Environment created. Activate the environment using `conda activate {env_name}` to begin.')


######################
#
# Helper Functions
#
######################
def consistency_check():

    ops_dir = find_conda_ops_dir()
    logger.debug('\nChecking consistency of the requirements, lock file, and environment...\n')

    logger.debug('Checking config.ini constistency')
    config = configparser.ConfigParser()
    config.read(ops_dir / CONFIG_FILENAME)
    env_name = config['DEFAULT']['ENV_NAME']

    status_file = ops_dir / STATUS_FILENAME
    requirements_file = ops_dir / REQUIREMENTS_FILENAME
    explicit_lock_file = ops_dir / EXPLICIT_LOCK_FILENAME
    lock_file = ops_dir / LOCK_FILENAME

    if requirements_file.exists():
        logger.debug("Requirements file present")
        if lock_file.exists():
            logger.debug("Checking requirements and lock file sync")
            if requirements_file.stat().st_mtime < lock_file.stat().st_mtime:
                logger.debug("Lock file is newer than the requirements file")
            else:
                logger.warning("The requirements file is newer than the lock file.")
                logger.info("To update the lock file:")
                logger.info(">>> conda ops sync")  # XXX want this to be conda ops lock
                sys.exit(0)
    else:
        logger.warning("No requirements file present")
        logger.info("To add requirements to the environment:")
        logger.info(">>> conda ops add <package>")
        sys.exit(0)


    from conda.cli.main_info import get_info_dict

    info_dict = get_info_dict()
    active_conda_env = info_dict['active_prefix_name']

    logger.info(f"Active conda environment: {active_conda_env}")
    if active_conda_env == env_name:
        pass
    else:
        logger.warning("Incorrect or missing conda environment.")
        logger.info("To create it:")
        logger.info(">>> conda ops create")
        logger.info("To activate it:")
        logger.info(f">>> conda ops activate")
        sys.exit(1)

    logger.debug("Enumerating packages from the active environment")
    conda_args = ["-n", env_name, "--explicit"]
    stdout, stderr, result_code = run_command("list", conda_args, use_exception_handler=True)
    if result_code != 0:
        logger.info(stdout)
        logger.info(stderr)
        sys.exit()
    conda_set = set([x for x in stdout.split("\n") if ('https' in x)])

    # packages from the lock file
    with open(explicit_lock_file, 'r') as f:
        lock_contents = f.read()
    lock_set = set([x for x in lock_contents.split("\n") if ('https' in x)])

    if conda_set == lock_set:
        logger.info("Environment and lock file are in sync.\n")
    else:
        logger.info('The lock file and environment are not in sync')
        in_env = conda_set.difference(lock_set)
        in_lock = lock_set.difference(conda_set)
        if len(in_env) > 0:
            logger.info("\nThe following packages are in the environment but not in the lock file:\n")
            logger.info("\n".join(in_env))
            logger.info("\n")
            logger.info("Run `conda ops clean` to restore the environment to the state of the lock file")
        if len(in_lock) > 0:
            logger.info("\nThe following packages are in the lock file but not in the environment:\n")
            logger.info("\n".join(in_lock))
            logger.info("\n")
            logger.info("Run `conda ops sync` to update the environment to match the lock file.\n")

def find_conda_ops_dir():
    '''
    Locate the conda ops configuration directory.

    Searches current and all parent directories.
    '''
    logger.debug("Searching for conda_ops dir.")
    ops_dir = find_upwards(Path.cwd(), CONDA_OPS_DIR_NAME)
    if ops_dir is None:
        logger.warning('No managed "conda ops" environment found (here or in parent directories).')
        logger.info("To start managing a new conda ops environment")
        logger.info(">>> conda ops init")
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
    if cwd == Path(cwd.root) or cwd == cwd.parent:
        return None

    fullpath = cwd / filename

    try:
        return fullpath if fullpath.exists() else find_upwards(cwd.parent, filename)
    except RecursionError:
        return None

def json_to_explicit(json_list):
    """
    Convert a json environment dump (as in ['actions']['link'] to the explicit file format that
    can be used for create and update conda environments.
    """
    explicit_str = ''
    for package in json_list:
        package_str = '/'.join([package['base_url'], package['platform'], (package['dist_name'] + '.conda')]).strip()
        explicit_str += package_str+"\n"
    return explicit_str
