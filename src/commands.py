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


######################
#
# Compound Functions
#
######################

def cmd_activate(*, config=None, name=None):
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


def cmd_create(config=None):
    '''
    Create the first lockfile and environment.

    XXX Possibily init if that hasn't been done yet
    '''
    env_name = config['settings']['env_name']
    if check_env_exists(env_name):
        logger.error(f"Environment {env_name} exists.")
        logger.info("To activate it:")
        logger.info(f">>> conda activate {env_name}")
        sys.exit(1)
    json_reqs = lockfile_generate(config)

    env_create(config)


def cmd_deactivate():
    """Deactivate managed conda environment"""
    # check current environment is correct one
    logger.error("Unimplemented: deactivate")

def cmd_sync():
    """Generate a lockfile from a requirements file, then update the environment from it."""
    logger.error("Unimplemented: sync")

def cmd_init():
    '''
    Initialize the conda ops project by creating a .conda-ops directory including the conda-ops project structure
    '''

    config = proj_create()
    reqs_create(config)

    ops_dir = config['paths']['ops_dir']
    logger.info(f'Initialized conda-ops project in {ops_dir}')
    print('To create the conda ops environment:')
    print('>>> conda ops create')


######################
#
# Project Level Functions
#
######################

def proj_create():
    """
    Initialize the conda ops project by creating a .conda-ops directory and config file.

    Return the config dict
    """
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
        'requirements_path': '${ops_dir}/environment.yml',
        'lockfile_path': '${ops_dir}/lockfile.json',
        'explicit_lockfile_path': '${ops_dir}/lockfile.explicit'
    }
    _config_settings ={
        'env_name': env_name,
    }
    config = {}

    config['settings'] = KVStore(_config_settings, config_file=config_file, config_section='OPS_SETTINGS')
    config['paths'] = PathStore(_config_paths, config_file=config_file, config_section='OPS_PATHS')

    return config


######################
#
# Requirements Level Functions
#
######################

def reqs_add(packages, channel=None, config=None):
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

def reqs_create(config):
    """
    Create the requirements file if it doesn't already exist
    """
    requirements_file = config['paths']['requirements_path']
    env_name = config['settings']['env_name']

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

def reqs_check(config, die_on_error=True):
    """
    Check for the existence and consistency of the requirements file.

    Return True if the requirements pass all checks and False otherwise
    """
    requirements_file = config['paths']['requirements_path']
    env_name = config['settings']['env_name']

    check = True
    if requirements_file.exists():
        logger.debug("Requirements file present")

        with open(requirements_file, 'r') as f:
            requirements = yaml.load(requirements_file)
        if not (requirements['name'] == env_name):
            logger.error(f"The name in the requirements file {requirements['name']} does not match the name of the managed conda environment {env_name}")
            if input("Would you like to update the environment name in your requirements file (y/n) ").lower() == 'y':
                requirements['name'] = env_name
                with open(requirements_file, 'w') as f:
                    yaml.dump(requirements, f)
            else:
                logger.warning(f"Please check the consistency of your requirements file {requirements_file} manually.")
                check = False
        deps = requirements.get('dependencies', None)
        if deps is None:
            logger.warning(f"No dependencies found in the requirements file.")
            logger.error(f"Unimplemented: what to do in this case.")
            check = False
    else:
        check = False
        logger.warning("No requirements file present")
        logger.info("To add requirements to the environment:")
        logger.info(">>> conda ops add <package>")
    if die_on_error and not check:
        sys.exit(1)
    return check

######################
#
# Lockfile Level Functions
#
######################

def lockfile_generate(config):
    """
    Generate a lock file from the requirements file.

    Currently always overwrites any existing files.
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
            json.dump(json_reqs, f)
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

def lockfile_check(config, die_on_error=True):
    """
    Check for the consistency of the lockfile.
    """
    lock_file = config['paths']['lockfile_path']

    check = True
    if lock_file.exists():
        with open(lock_file, 'r') as f:
            try:
                json_reqs = json.load(f)
                try:
                    actions = json_reqs['actions']['LINK']
                except:
                    check = False
                    logger.error(f"Lockfile {lock_file} is missing the necessary sections")
                    logger.info("To regenerate the lock file:")
                    logger.info(">>> conda ops lock")
            except Exception as e:
                check = False
                logger.error(f"Unable to load lockfile {lock_file}")
                logger.debug(e)
                logger.info("To regenerate the lock file:")
                logger.info(">>> conda ops lock")
    else:
        check = False
        logger.error("There is no lock file.")
        logger.info("To create the lock file:")
        logger.info(">>> conda ops lock")

    if die_on_error and not check:
        sys.exit(1)
    return check

def lockfile_reqs_check(config, reqs_consistent=None, lockfile_consistent=None, die_on_error=True):
    """
    Check the consistency of the lockfile against the requirements file.
    """
    requirements_file = config['paths']['requirements_path']
    lock_file = config['paths']['lockfile_path']

    check = True
    if reqs_consistent is None:
        reqs_consistent = reqs_check(config, die_on_error=die_on_error)

    if lockfile_consistent is None:
        lockfile_consistent = lockfile_check(config, die_on_error=die_on_error)

    if lockfile_consistent and reqs_consistent:
        if requirements_file.stat().st_mtime < lock_file.stat().st_mtime:
            logger.debug("Lock file is newer than the requirements file")
            logger.error("Unimplemented: Check that the names in the requirements are in the lock file")
        else:
            check = False
            logger.warning("The requirements file is newer than the lock file.")
            logger.info("To update the lock file:")
            logger.info(">>> conda ops lock")
    else:
        if not reqs_consistent:
            logger.error(f"Cannot check lockfile against requirements as the requirements file is inconsistent.")
            check = False
        elif not lockfile_consistent:
            logger.error(f"Cannot check lockfile against requirements as the lock file is inconsistent.")
            check = False


    if die_on_error and not check:
        sys.exit(1)
    return check

######################
#
# Environment Level Functions
#
######################

def env_create(config):
    """
    Create the conda ops managed environment from the lock file
    """
    env_name = config['settings']['env_name']
    if check_env_exists(env_name):
        logger.error(f"Environment {env_name} exists.")
        logger.info("To activate it:")
        logger.info(f">>> conda activate {env_name}")
        sys.exit(1)
    explicit_lock_file = config['paths']['explicit_lockfile_path']
    generate_explicit_lock_file(config)

    logger.info(f"Creating the environment {env_name}")
    create_args = ["-n", env_name, "--file", str(explicit_lock_file)]
    stdout, stderr, result_code = run_command("create", create_args, use_exception_handler=True)
    if result_code != 0:
        logger.info(stdout)
        logger.info(stderr)
        sys.exit(result_code)
    logger.info(stdout)

    logger.info(f'Environment created. To activate the environment:')
    logger.info(">>> conda activate {env_name}")

def env_delete(config=None):
    """
    Deleted the conda ops managed conda environment (aka. conda remove -n env_name --all)
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

def consistency_check(config=None, die_on_error=False):
    """
    Check the consistency of the requirements file vs. lock file vs. conda environment
    """
    if config is None:
        logger.error("No managed conda environment found.")
        logger.info("To place the current directory under conda ops management:")
        logger.info(">>> conda ops init")
        logger.info("To change to a managed directory:")
        logger.info(">>> cd path/to/managed/conda/project")
        sys.exit(1)

    env_name = config['settings']['env_name']
    logger.info(f"Managed Conda Environment: {env_name}")

    explicit_lock_file = config['paths']['explicit_lockfile_path']
    lock_file = config['paths']['lockfile_path']

    reqs_consistent = reqs_check(config, die_on_error=die_on_error)
    lockfile_consistent = lockfile_check(config, die_on_error=die_on_error)

    lockfile_reqs_consistent = lockfile_reqs_check(config, reqs_consistent=reqs_consistent, lockfile_consistent=lockfile_consistent, die_on_error=die_on_error)

    info_dict = get_conda_info()
    active_conda_env = info_dict['active_prefix_name']
    platform = info_dict['platform']

    logger.info(f"Active Conda environment: {active_conda_env}")
    logger.info(f"Conda platform: {platform}")
    if active_conda_env == env_name:
        pass
    else:
        env_exists = check_env_exists(env_name)
        if env_exists:
            logger.warning(f"Managed conda environment ('{env_name}') exists but is not active.")
            logger.info("To activate it:")
            logger.info(f">>> conda activate {env_name}")
        else:
            logger.warning(f"Managed conda environment ('{env_name}') does not yet exist.")
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
        s = "No managed conda environment found (here or in parent directories)."
        if die_on_error:
            logger.error(s)
        else:
            logger.warning(s)
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


def generate_explicit_lock_file(config):
    """
    Generate an explicit lock file from the usual one (aka. of the format generated by `conda list --explicit`
    """
    logger.info('creating explicit file for installation')
    lock_file = config['paths']['lockfile_path']

    with open(lock_file, 'r') as f:
        json_reqs = json.load(f)

    explicit_str = "# This file may be used to create an environment using:\n# $ conda create --name <env> --file <this file>\n@EXPLICIT\n"
    explicit_str += json_to_explicit(json_reqs['actions']['LINK'])

    explicit_lock_file = config['paths']['explicit_lockfile_path']
    with open(explicit_lock_file, 'w') as f:
        f.write(explicit_str)

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
