## Main Functionality

from pathlib import Path
import sys
import configparser
import json
from ruamel.yaml import YAML
from .split_requirements import create_split_files
from .python_api import run_command
from .kvstore import KVStore
from ._paths import PathStore
import conda.cli.python_api
from conda.cli.main_info import get_info_dict

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
CONFIG_FILENAME = 'config.ini'

yaml = YAML()
yaml.default_flow_style=False
yaml.width=4096
yaml.indent(offset=4)

def ops_activate(*, config=None, name=None):
    """Activate the managed environment"""
    env_name = config['settings']['env_name']
    if name is None:
        name = env_name
    if name != env_name:
        logger.warning(f'Activating environment {name} which does not match the conda ops managed environment {env_name}')
    ## Note: this is tricky as activate balks
    logger.error("XXX: figuring this out")
    stdout, stderr, result_code = run_command('activate', name, use_exception_handler=True)
    if result_code != 0:
        logger.info(stdout)
        logger.info(stderr)
        sys.exit(result_code)

    logger.error("Unimplemented: activate")

def ops_deactivate():
    """Deactivate managed conda environment"""
    # check current environment is correct one
    logger.error("Unimplemented: deactivate")

def ops_sync():
    """Generate a lockfile from a requirements file, then update the environment from it."""
    logger.error("Unimplemented: sync")

def ops_add(packages, channel=None, config=None):
    """
    Add packages to the requirements file from a given channel. By default add the channel to the
    end of the channel order. Treat pip as a special channel.
    """
    requirements_file = config['paths']['requirements_path']

    logger.info(f'adding packages {packages} from channel {channel} to the requirements file {requirements_file}')

    with open(requirements_file, 'r') as yamlfile:
        reqs = yaml.load(yamlfile)

    # pull off the pip section ot keep it at the beginning of the reqs file
    pip_dict = None
    for k, dep in enumerate(reqs['dependencies']):
        if isinstance(dep, dict):  # nested yaml
            if dep.get('pip', None):
                pip_dict = reqs['dependencies'].pop(k)
                break

    if channel is None:
        reqs['dependencies'] = list(set(reqs['dependencies'] + packages))
    elif channel=='pip':
        if pip_dict is None:
            pip_dict = {'pip': list(set(packages))}
        else:
            pip_dict['pip'] = list(set(pip_dict['pip'] + packages))
        reqs['dependencies'].append(pip_dict)
    else: # interpret channel as a conda channel
        package_list = [f'{channel}::{package}' for package in packages]
        reqs['dependencies'] = list(set(reqs['dependencies'] + package_list))
        if not channel in reqs['channel-order']:
            reqs['channel-order'].append(channel)

    # add back the pip section
    if pip_dict is not None:
        reqs['dependencies'] = [pip_dict] + reqs['dependencies']

    logger.error("NOT YET IMPLEMENTED: check that the given packages have not already been specified in a different channel. Figure out what to suggest in that case")

    with open(requirements_file, 'w') as yamlfile:
        yaml.dump(reqs, yamlfile)

    print(f'Added packages {packages} to requirements file.')
    print('To update the lockfile accordingly:')
    print('>>> conda ops lock')

def ops_delete(config=None):
    """
    Deleted the cond ops managed conda environment (aka. conda remove -n env_name --all)
    """
    env_name = config['settings']['env_name']

    env_exists = check_env_exists(env_name)
    if not env_exists:
        logger.warning(f"The conda environment {env_name} does not exist, and cannot be deleted.")
        logger.info("To create the environment:")
        logger.info(">>> conda ops create")
    else:
        print(f"Deleting the conda environment {env_name}")
        stdout, stderr, result_code = run_command("remove", '-n', env_name, '--all', use_exception_handler=True)
        if result_code != 0:
            logger.info(stdout)
            logger.info(stderr)
            sys.exit(result_code)
        print("Environment deleted.")
        print("To create the environment again:")
        print(">>> conda ops create")

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

    # currently defaults to creating an env_name based on the location of the project
    env_name = Path.cwd().name

    _config_paths = {
        'ops_dir': '${catalog_path}',
        'requirements_path': '${catalog_path}/environment.yml',
        'lockfile_path': '${catalog_path}/lockfile.json',
        'explicit_lockfile_path': '${catalog_path}/lockfile.explicit'
    }
    _config_settings ={
        'env_name': env_name,
    }
    config = KVStore(_config_settings, config_file=config_file, config_section='OPS_SETTINGS')
    path_config = PathStore(_config_paths, config_file=config_file, config_section='OPS_PATHS')

    # create basic requirements file
    requirements_file = path_config['requirements_path']
    if not requirements_file.exists():
        requirements_dict = {'name': env_name,
                             'channels': ['defaults'],
                             'channel-order': ['defaults'],
                             'dependencies': ['python', 'pip']}
        logger.info('writing')
        with open(requirements_file, 'w') as f:
            yaml.dump(requirements_dict, f)
    else:
        logger.info(f'Requirements file {requirements_file} already exists')
    logger.info(f'Initialized conda-ops project in {conda_ops_path.resolve()}')
    print('To create the conda ops environment:')
    print('>>> conda ops create')

def ops_create(config=None):
    '''
    Create the first lockfile and environment
    '''
    logger.info('TODO: check if the environment already exists...')

    ops_dir = config['paths']['ops_dir']
    env_name = config['settings']['env_name']

    json_reqs = generate_lock_file(config)

    logger.info('creating explicit file for installation')
    explicit_str = "# This file may be used to create an environment using:\n# $ conda create --name <env> --file <this file>\n@EXPLICIT\n"
    explicit_str += json_to_explicit(json_reqs['actions']['LINK'])

    explicit_lock_file = config['paths']['explicit_lockfile_path']
    with open(explicit_lock_file, 'w') as f:
        f.write(explicit_str)

    logger.info(f"Creating the environment {env_name}")
    create_args = ["-n", env_name, "--file", str(explicit_lock_file)]
    stdout, stderr, result_code = run_command("create", create_args, use_exception_handler=True)
    logger.info(stdout)

    logger.info(f'Environment created. To activate the environment:')
    logger.info(">>> conda ops activate")

def ops_lock(config=None):
    """
    Create a lock file from the requirements file
    """
    generate_lock_file(config)

    logger.info("lock file generated")


######################
#
# Helper Functions
#
######################

def load_config(die_on_error=True):
    """Load the conda ops configuration file."""
    ops_dir = find_conda_ops_dir(die_on_error=die_on_error)

    if ops_dir is not None:
        logger.debug('Checking config.ini constistency')
        path_config = PathStore(config_file=(ops_dir / CONFIG_FILENAME), config_section='OPS_PATHS')
        ops_config = KVStore(config_file=(ops_dir / CONFIG_FILENAME), config_section='OPS_SETTINGS')
        config = {'paths': path_config, 'settings': ops_config}
    else:
        config = None
    return config

def consistency_check(config=None):
    """
    Check the consistency of the requirements file vs. lock file vs. conda environment
    """
    env_name = config['settings']['env_name']
    logger.debug(f"Managed Conda Environment name: {env_name}")

    requirements_file = config['paths']['requirements_path']
    explicit_lock_file = config['paths']['explicit_lockfile_path']
    lock_file = config['paths']['lockfile_path']

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

    info_dict = get_conda_info()
    active_conda_env = info_dict['active_prefix_name']
    platform = info_dict['platform']

    logger.info(f"Active conda environment: {active_conda_env}")
    logger.info(f"Platform: {platform}")
    if active_conda_env == env_name:
        pass
    else:
        logger.warning("Incorrect or missing conda environment.")
        env_exists = check_env_exists(env_name)
        if env_exists:
            logger.info(f"Environment {env_name} exists.")
            logger.info("To activate it:")
            logger.info(f">>> conda ops activate")
        else:
            logger.info(f"Environment {env_name} does not yet exist.")
            logger.info("To create it:")
            logger.info(">>> conda ops create")
        sys.exit(1)

    logger.debug("Enumerating packages from the active environment")
    conda_args = ["-n", env_name, "--explicit"]
    stdout, stderr, result_code = run_command("list", conda_args, use_exception_handler=True)
    if result_code != 0:
        logger.info(stdout)
        logger.info(stderr)
        sys.exit()
    conda_set = set([x for x in stdout.split("\n") if ('https' in x)])
    logger.debug(f"Found {len(conda_set)} packages in environment: {active_conda_env}")

    if not explicit_lock_file.exists():
        logger.warning(f"No Lock File Found ({explicit_lock_file.name})")
        logger.info("To lock the environment:")
        logger.info(">>> conda ops lock")
        sys.exit(0)
    # packages from the lock file
    with open(explicit_lock_file, 'r') as f:
        lock_contents = f.read()
    lock_set = set([x for x in lock_contents.split("\n") if ('https' in x)])

    if conda_set == lock_set:
        logger.debug("Environment and lock file are in sync.\n")
    else:
        logger.warning('The lock file and environment are not in sync')
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

def get_conda_info():
    """Get conda configuration information.

    This currently peeks into the conda internals.
    XXX Should this maybe be a conda info API call instead?
    """
    return get_info_dict()


def find_conda_ops_dir(die_on_error=True):
    '''
    Locate the conda ops configuration directory.

    Searches current and all parent directories.

    die_on_error: Boolean
        if ops_dir is not found:
            if True, exit with error
            if False, return None
    '''
    logger.debug("Searching for conda_ops dir.")
    ops_dir = find_upwards(Path.cwd(), CONDA_OPS_DIR_NAME)
    if ops_dir is None:
        logger.warning('No managed "conda ops" environment found (here or in parent directories).')
        logger.info("To start managing a new conda ops environment")
        logger.info(">>> conda ops init")
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

def generate_lock_file(config):
    """
    Generate a lock file from the requirements file.
    """
    ops_dir = config['paths']['ops_dir']
    requirements_file = config['paths']['requirements_path']
    lock_file = config['paths']['lockfile_path']
    requirements = yaml.load(requirements_file)
    env_name = config['settings']['env_name']
    logger.debug(env_name)

    logger.info('generating multi-step requirements files')
    create_split_files(requirements_file, ops_dir)

    with open(ops_dir / '.ops.channel-order.include', 'r') as f:
        order_list = f.read().split()

    logger.info('generating the lock file')
    # creating the environment with the first stage
    with open(ops_dir / f'.ops.{order_list[0]}-environment.txt') as f:
        package_list = f.read().split()

    create_args = ["-n", env_name] + package_list + ['--dry-run', '--json']

    if check_env_exists(env_name):
        stdout, stderr, result_code = run_command("install", create_args, use_exception_handler=True)
        if result_code != 0:
            logger.info(stdout)
            logger.info(stderr)
            sys.exit()
    else:
        stdout, stderr, result_code = run_command("create", create_args, use_exception_handler=True)
        if result_code != 0:
            logger.info(stdout)
            logger.info(stderr)
            sys.exit()
    json_reqs = json.loads(stdout)
    if json_reqs.get('message', None) == 'All requested packages already installed.':
        logger.error("All requested packages are already installed. Cannot generate lock file")
        logger.warning("TODO: Decide what to do when all requested packages are already installed in the environment. Probably need to sync? And check that the lock file and environment are in sync.")
    elif 'actions' in json_reqs:
        with open(lock_file, 'w') as f:
            json.dump(json_reqs['actions'], f)
        print(f"Lockfile {lock_file} successfully created.")
    else:
        logger.error(f"Unexpected output:\n {json_reqs}")
        sys.exit()

    if len(order_list) > 1:
        ## XXX implement the next steps here
        logger.error(f"TODO: Implement multi-stage install here...currently ignorning channels other than {order_list[0]}")

    ## XXX Implement the pip step here
    logger.error('TODO: Implement the pip installation step here')
    logger.error("NOT IMPLEMENTED YET: lock files currently only contain packages from the defaults channel and do not include any other channels")
    return json_reqs

def check_env_exists(env_name):
    """
    Given the name of a conda environment, check if it exists
    """
    stdout, stderr, result_code = run_command('info', '--envs', '--json', use_exception_handler=True)
    if result_code != 0:
        logger.info(stdout)
        logger.info(stderr)
        sys.exit()
    json_output = json.loads(stdout)

    env_list = [Path(x).name for x in json_output['envs']]
    if env_name in env_list:
        return True
    else:
        return False
