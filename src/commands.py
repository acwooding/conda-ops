## Main Functionality

from pathlib import Path
import sys
import configparser
import json
from ruamel.yaml import YAML
from .split_requirements import create_split_files, env_split, get_channel_order
from .python_api import run_command
from .kvstore import KVStore
from ._paths import PathStore
import conda.cli.python_api
from conda.cli.main_info import get_info_dict
import urllib
import shutil
import subprocess
import re
from io import StringIO
from contextlib import redirect_stdout
from packaging.requirements import Requirement


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



##################################################################
#
# Project Level Functions
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
        'requirements': '${ops_dir}/environment.yml',
        'lockfile': '${ops_dir}/lockfile.json',
        'explicit_lockfile': '${ops_dir}/lockfile.explicit',
        'pip_explicit_lockfile': '${ops_dir}/lockfile.pypi'
    }
    _config_settings ={
        'env_name': env_name,
    }

    config = {}

    config['settings'] = KVStore(_config_settings, config_file=config_file, config_section='OPS_SETTINGS')
    config['paths'] = PathStore(_config_paths, config_file=config_file, config_section='OPS_PATHS')

    return config


def proj_load(die_on_error=True):
    """Load the conda ops configuration file."""
    ops_dir = find_conda_ops_dir(die_on_error=die_on_error)

    if ops_dir is not None:
        logger.debug('Loading project config')
        path_config = PathStore(config_file=(ops_dir / CONFIG_FILENAME), config_section='OPS_PATHS')
        ops_config = KVStore(config_file=(ops_dir / CONFIG_FILENAME), config_section='OPS_SETTINGS')
        config = {'paths': path_config, 'settings': ops_config}
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
        #logger.info(">>> conda ops init")
        logger.info("To change to a managed directory:")
        logger.info(">>> cd path/to/managed/conda/project")
    else:
        env_name = config['settings'].get('env_name', None)
        if env_name is None:
            check = False
            logger.error("Config is missing an environment name")
            logger.info("To reinitialize your conda ops project:")
            logger.info(">>> conda ops proj create")
            #logger.info(">>> conda ops init")
        paths = config['paths']
        if len(paths) < 4:
            check = False
            logger.error("Config is missing paths")
            logger.info("To reinitialize your conda ops project:")
            logger.info(">>> conda ops proj create")
            #logger.info(">>> conda ops init")

    if die_on_error and not check:
        sys.exit(1)
    return check


##################################################################
#
# Requirements Level Functions
#
##################################################################

def reqs_add(packages, channel=None, config=None):
    """
    Add packages to the requirements file from a given channel. By default add the channel to the
    end of the channel order. Treat pip as a special channel.

    TODO: Handle version strings properly
    """
    requirements_file = config['paths']['requirements']
    logger.debug(packages)
    package_str= ' '.join(packages)
    logger.info(f'adding packages {package_str} from channel {channel} to the requirements file {requirements_file}')

    packages = [x.strip() for x in packages]

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
    else: # interpret channel as a conda channel
        package_list = [f'{channel}::{package}' for package in packages]
        reqs['dependencies'] = list(set(reqs['dependencies'] + package_list))
        if not channel in reqs['channel-order']:
            reqs['channel-order'].append(channel)

    # add back the pip section
    if pip_dict is not None:
        reqs['dependencies'] = [pip_dict] + reqs['dependencies']

    logger.error("NOT YET IMPLEMENTED: check that the given packages have not already been specified in a different channel or version. Override with the new option and possilby warn")

    with open(requirements_file, 'w') as yamlfile:
        yaml.dump(reqs, yamlfile)

    print(f'Added packages {package_str} to requirements file.')

def reqs_remove(packages, config=None):
    """
    Remove packages from the requirements file. Treat pip as a special channel.

    TODO: Handle version strings properly
    """
    requirements_file = config['paths']['requirements']
    logger.debug(packages)
    package_str= ' '.join(packages)
    logger.info(f'Removing packages {package_str} from the requirements file {requirements_file}')

    packages = [x.strip() for x in packages]

    with open(requirements_file, 'r') as yamlfile:
        reqs = yaml.load(yamlfile)

    # pull off the pip section ot keep it at the beginning of the reqs file
    pip_dict = None
    for k, dep in enumerate(reqs['dependencies']):
        if isinstance(dep, dict):  # nested yaml
            if dep.get('pip', None):
                pip_dict = reqs['dependencies'].pop(k)
                break

    # first remove non-pip dependencies

    deps = list(set(reqs['dependencies']))
    for package in packages:
        for dep in deps:
            if '::' in dep:
                dep_check = dep.split('::')[-1].strip()
            else:
                dep_check = dep.strip()
            if dep_check.startswith(package): # probably need a regex match to get this right
                if dep_check != package:
                    logger.warning(f'Removing {dep} from requirements')
                deps.remove(dep)
    reqs['dependencies'] = deps

    # remove any channels that aren't needed anymore
    channel_in_use = []
    for dep in deps:
        if '::' in dep:
            channel, _  = dep.split('::')
            channel_in_use.append(channel)
    new_channel_order = []
    for channel in reqs['channel-order']:
        if channel == 'defaults':
            new_channel_order.append(channel)
        if channel in channel_in_use:
            new_channel_order.append(channel)
    reqs['channel-order'] = new_channel_order

    # now remove pip dependencies is the section exists
    if pip_dict is not None:
        pip_dict['pip'] = list(set(pip_dict['pip'] + packages))
        deps =  list(set(pip_dict['pip']))
        for package in packages:
            for dep in deps:
                if dep.startswith(package):
                    if dep_check != package: # probably need a proper reges match to get this right
                        logger.warning(f'Removing {dep} from requirements')
                    deps.remove(dep)
        pip_dict['pip'] = deps

    # add back the pip section
    if pip_dict is not None:
        if len(pip_dict['pip']) > 0:
            reqs['dependencies'] = [pip_dict] + reqs['dependencies']

    with open(requirements_file, 'w') as yamlfile:
        yaml.dump(reqs, yamlfile)

    print(f'Removed packages {package_str} to requirements file.')

def reqs_create(config):
    """
    Create the requirements file if it doesn't already exist
    """
    requirements_file = config['paths']['requirements']
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
    requirements_file = config['paths']['requirements']
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
        logger.info("To add a default requirements file to the environment:")
        logger.info(">>> conda ops reqs create")
    if die_on_error and not check:
        sys.exit(1)
    return check

##################################################################
#
# Lockfile Level Functions
#
##################################################################

def lockfile_generate(config, regenerate=False):
    """
    Generate a lock file from the requirements file.

    Currently always overwrites the existing lock file when complete.

    If regenenerate=True, use a clean environment to generate the lock file.
    """
    ops_dir = config['paths']['ops_dir']
    requirements_file = config['paths']['requirements']
    lock_file = config['paths']['lockfile']
    env_name = config['settings']['env_name']

    if regenerate:
        # create a blank environment name to create the lockfile from scratch
        raw_test_env = env_name+'-test'
        for i in range(100):
            test_env = raw_test_env+f'-{i}'
            if not check_env_exists(test_env):
                break
    else:
        test_env = env_name

    if not requirements_file.exists():
        logger.error(f"Requirements file does not exist: {requirements_file}")
        logger.info("To create a minimal default requirements file:")
        logger.info(">>> conda ops reqs create")
        sys.exit(1)

    logger.info('Generating multi-step requirements files')
    create_split_files(requirements_file, ops_dir)

    with open(ops_dir / '.ops.channel-order.include', 'r') as f:
        order_list = f.read().split()

    if (ops_dir / f'.ops.pypi-requirements.txt').exists():
        order_list += ['pip']
    json_reqs = None
    for i, channel in enumerate(order_list):
        logger.debug(f'Installing from channel {channel}')
        if channel != 'pip':
            json_reqs = conda_step_env_lock(channel, config, env_name=test_env)
        else:
            json_reqs = pip_step_env_lock(config, env_name=test_env)
        if json_reqs is None:
                if i > 0:
                    logger.warning(f"Last successful channel was {order_list[i-1]}")
                    logger.error(f"Unimplemented: Decide what to do when not rolling back the environment here")
                    last_good_channel = order_list[i-1]
                    sys.exit(1)
                else:
                    logger.error("No successful channels were installed")
                    sys.exit(1)
                break
        else:
            last_good_channel = order_list[i]

    last_good_lockfile = f'.ops.lock.{last_good_channel}'
    logger.debug(f"Updating lock file from {last_good_lockfile}")
    shutil.copy(ops_dir / (ops_dir / last_good_lockfile), lock_file)

    # clean up
    for channel in order_list:
        if channel == 'pip':
            Path(ops_dir / f'.ops.pypi-requirements.txt').unlink()
            Path(ops_dir / f'.ops.sdist-requirements.txt').unlink()
        else:
            Path(ops_dir / f'.ops.{channel}-environment.txt').unlink()
        Path(ops_dir / f'.ops.lock.{channel}').unlink()

    Path(ops_dir / '.ops.channel-order.include').unlink()
    if regenerate:
        env_delete(env_name=test_env)


def lockfile_check(config, die_on_error=True):
    """
    Check for the consistency of the lockfile.
    """
    lock_file = config['paths']['lockfile']

    check = True
    if lock_file.exists():
        with open(lock_file, 'r') as f:
            try:
                json_reqs = json.load(f)
            except Exception as e:
                check = False
                logger.error(f"Unable to load lockfile {lock_file}")
                logger.debug(e)
                logger.info("To regenerate the lock file:")
                logger.info(">>> conda ops lockfile regenerate")
                #logger.info(">>> conda ops lock")
            if json_reqs:
                for package in json_reqs:
                    if package['manager'] == 'conda':
                        package_url = '/'.join([package['base_url'], package['platform'],
                                                (package['dist_name']+package['extension'])]).strip()+f"#{package['md5']}"
                        if package['url'].strip() != package_url.strip():
                            check = False
                            logger.warning(f"package information for {package['name']} is inconsistent")
                            logger.debug(f"{package_url}, \n{package['url']}")
                            logger.info("To regenerate the lock file:")
                            logger.info(">>> conda ops lockfile regenerate")
                            #logger.info(">>> conda ops lock")
    else:
        check = False
        logger.error("There is no lock file.")
        logger.info("To create the lock file:")
        logger.info(">>> conda ops lockfile generate")
        #logger.info(">>> conda ops lock")

    if die_on_error and not check:
        sys.exit(1)
    return check

def lockfile_reqs_check(config, reqs_consistent=None, lockfile_consistent=None, die_on_error=True):
    """
    Check the consistency of the lockfile against the requirements file.
    """
    requirements_file = config['paths']['requirements']
    lock_file = config['paths']['lockfile']

    check = True
    if reqs_consistent is None:
        reqs_consistent = reqs_check(config, die_on_error=die_on_error)

    if lockfile_consistent is None:
        lockfile_consistent = lockfile_check(config, die_on_error=die_on_error)

    if lockfile_consistent and reqs_consistent:
        if requirements_file.stat().st_mtime <= lock_file.stat().st_mtime:
            logger.debug("Lock file is newer than the requirements file")
        else:
            check = False
            logger.warning("The requirements file is newer than the lock file.")
            logger.info("To update the lock file:")
            logger.info(">>> conda ops lockfile regenerate")
            #logger.info(">>> conda ops lock")
        with open(requirements_file, 'r') as yamlfile:
            reqs_env = yaml.load(yamlfile)
        channel_order = get_channel_order(reqs_env)
        _ , channel_dict = env_split(reqs_env, channel_order)
        with open(lock_file, 'r') as lf:
            lock_dict = json.load(lf)
        lock_names = [package['name'] for package in lock_dict]

        # so far we don't check that the channel info is correct, just that the package is there
        missing_packages = []
        logger.debug(channel_dict)
        for channel in channel_order:
            if channel == 'pip':
                pip_cd = channel_dict.get(channel, None)
                if pip_cd:
                    channel_list = channel_dict[channel][channel]
                else:
                    channel_list = []
            else:
                channel_list = channel_dict[channel]
            for package in channel_list:
                if package not in lock_names:
                    missing_packages.append(package)
        if len(missing_packages) > 0:
            check = False
            logger.error(f"The following requirements are not in the lockfile:")
            logger.error(f"{' '. join(missing_packages)}")
            logger.info("To update the lock file:")
            logger.info(">>> conda ops lockfile generate")
    else:
        if not reqs_consistent:
            logger.error(f"Cannot check lockfile against requirements as the requirements file is missing or inconsistent.")
            check = False
        elif not lockfile_consistent:
            logger.error(f"Cannot check lockfile against requirements as the lock file is missing or inconsistent.")
            check = False


    if die_on_error and not check:
        sys.exit(1)
    return check

##################################################################
#
# Environment Level Functions
#
##################################################################

def env_activate(*, config=None, name=None):
    """Activate the managed environment"""
    env_name = config['settings']['env_name']
    if name is None:
        name = env_name
    if name != env_name:
        logger.warning(f'Requested environment {name} which does not match the conda ops managed environment {env_name}')
    if check_active_env(env_name):
        logger.warning(f"The conda ops environment {env_name} is already active.")
    else:
        logger.info("To activate the conda ops environment:")
        logger.info(f">>> conda activate {env_name}")

def env_deactivate(config):
    """Deactivate managed conda environment"""

    env_name = config['settings']['env_name']
    conda_info = get_conda_info()
    active_env = conda_info['active_prefix_name']

    if active_env != env_name:
        logger.warning("The active environment is {active_env}, not the conda ops managed environment {env_name}")

    logger.info(f"To deactivate the environment {active_env}:")
    logger.info(">>> conda deactivate")

def env_create(config=None, env_name=None, lock_file=None):
    """
    Create the conda ops managed environment from the lock file
    """
    if env_name is None:
        env_name = config['settings']['env_name']
    if check_env_exists(env_name):
        logger.error(f"Environment {env_name} exists.")
        logger.info("To activate it:")
        logger.info(f">>> conda activate {env_name}")
        sys.exit(1)

    if lock_file is None:
        lock_file = config['paths']['lockfile']

    if not lock_file.exists():
        logger.error(f"The lockfile does not exist: {lock_file}")
        logger.info("To generate a lockfile:")
        logger.info(">>> conda ops lockfile generate")
        sys.exit(1)
    explicit_files = generate_explicit_lock_files(config, lock_file=lock_file)

    explicit_lock_file = config['paths']['explicit_lockfile']
    logger.info(f"Creating the environment {env_name}")
    conda_args = ["-n", env_name, "--file", str(explicit_lock_file)]
    stdout, stderr, result_code = run_command("create", conda_args, use_exception_handler=True)
    if result_code != 0:
        logger.info(stdout)
        logger.info(stderr)
        sys.exit(result_code)
    logger.info(stdout)

    pip_lock_file = config['paths']['pip_explicit_lockfile']
    if pip_lock_file in explicit_files:
        logger.info("Installing pip managed dependencies...")

        # Workaround for the issue in conda version 23.5.0 (and greater?) see issues.
        # We need to capture the pip install output to get the exact filenames of the packages
        stdout_backup  = sys.stdout
        sys.stdout = capture_output = StringIO()
        with redirect_stdout(capture_output):
            conda_args = ["-n", env_name, "pip", "install", "-r", str(pip_lock_file), "--verbose"]
            stdout, stderr, result_code = run_command("run", conda_args, use_exception_handler=True)
            if result_code != 0:
                logger.info(stdout)
                logger.info(stderr)
                return None
        sys.stdout = stdout_backup
        stdout_str = capture_output.getvalue()
        logger.info(stdout_str)

    logger.info(f'Environment created. To activate the environment:')
    logger.info(f">>> conda activate {env_name}")


def env_lock(config=None, lock_file=None, env_name=None, pip_dict=None):
    """
    Generate a lockfile from the contents of the environment.
    """
    if env_name is None:
        env_name = config['settings']['env_name']
    if lock_file is None:
        lock_file = config['paths']['lockfile']

    if check_env_exists(env_name):
        # json requirements
        # need to use a subprocess to get any newly installed python package information
        # that was installed via pip
        conda_args = ["-n", env_name, '--json']
        result = subprocess.run(['conda', 'list'] + conda_args, capture_output=True)
        result_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
        if result_code != 0:
            logger.info(stdout)
            logger.info(stderr)
            sys.exit(1)

        json_reqs = json.loads(stdout)

        # explicit requirements to get full urls and md5
        conda_args = ["-n", env_name, '--explicit', '--md5']
        stdout, stderr, result_code = run_command("list", conda_args, use_exception_handler=True)
        if result_code != 0:
            logger.info(stdout)
            logger.info(stderr)
            sys.exit(1)
        explicit = [x for x in stdout.split("\n") if ('https' in x)]

        logger.debug(f"Environment {env_name} to be locked with {len(json_reqs)} packages")
        for package in json_reqs:
            if package['channel'] == 'pypi':
                package['manager'] = 'pip'
                if pip_dict is not None:
                    pip_dict_entry = pip_dict.get(package['name'], None)
                    if pip_dict_entry is not None:
                        if pip_dict_entry['version'] != package['version']:
                            logger.error(f"The pip extra info entry version {pip_dict_entry['version']} does not match the conda package version{package['version']}")
                            logger.debug(pip_dict_entry)
                            logger.debug(package)
                            sys.exit(1)
                        else:
                            package['url'] = pip_dict_entry['url']
                            package['sha256'] = pip_dict_entry['sha256']
                            package['filenmae'] = pip_dict_entry['filename']
            else:
                starter_str = '/'.join([package['base_url'], package['platform'], package['dist_name']])
                for line in explicit:
                    if starter_str in line:
                        break
                md5_split = line.split('#')
                package['md5'] = md5_split[-1]
                package['extension'] = md5_split[0].split(f"{package['dist_name']}")[-1]
                package['url'] = line
                package['manager'] = 'conda'

        blob = json.dumps(json_reqs, indent=2, sort_keys=True)
        with open(lock_file, 'w') as f:
            f.write(blob)
    else:
        logger.error(f"No environment {env_name} exists")

    return json_reqs

def env_check(config=None, die_on_error=True):
    """
    Check that the conda ops environment exists and is active.
    """
    if config is None:
        config = proj_load()

    check = True

    env_name = config['settings']['env_name']

    info_dict = get_conda_info()
    active_conda_env = info_dict['active_prefix_name']
    platform = info_dict['platform']

    logger.info(f"Active Conda environment: {active_conda_env}")
    logger.info(f"Conda platform: {platform}")
    if check_env_active(env_name):
        pass
    else:
        env_exists = check_env_exists(env_name)
        if env_exists:
            check = False
            logger.warning(f"Managed conda environment ('{env_name}') exists but is not active.")
            logger.info("To activate it:")
            logger.info(f">>> conda activate {env_name}")
        else:
            check = False
            logger.warning(f"Managed conda environment ('{env_name}') does not yet exist.")
            logger.info("To create it:")
            logger.info(">>> conda ops env create")
            #logger.info(">>> conda ops create")
    if die_on_error and not check:
        sys.exit(1)
    return check


def env_lockfile_check(config=None, env_consistent=None, lockfile_consistent=None, die_on_error=True):
    """
    Check that the environment and the lockfile are in sync
    """
    if config is None:
        config = proj_load()

    env_name = config['settings']['env_name']


    if lockfile_consistent is None:
        lockfile_consistent = lockfile_check(config, die_on_error=die_on_error)

    if not lockfile_consistent:
        logger.warning(f"Lock file is missing or inconsistent. Cannot determine the consistency of the lockfile and environment.")
        logger.info("To lock the environment:")
        logger.info(">>> conda ops lockfile generate")
        #logger.info(">>> conda ops lock")
        if die_on_error:
            sys.exit(1)
        else:
            return False

    if env_consistent is None:
        env_consistent = env_check(config, die_on_error=die_on_error)

    if not env_consistent:
        logger.warning(f"Environment does not exist or is not active. Cannot determine the consistency of the lockfile and environment.")
        if die_on_error:
            sys.exit(1)
        else:
            return False

    check = True

    logger.debug(f"Enumerating packages from the conda ops environment {env_name}")
    conda_args = ["-n", env_name, "--explicit", "--md5"]
    stdout, stderr, result_code = run_command("list", conda_args, use_exception_handler=True)
    if result_code != 0:
        logger.error("Could not get packages from the environment")
        logger.info(stdout)
        logger.info(stderr)
        if die_on_error:
            sys.exit(result_code)
        else:
            return False

    conda_set = set([x for x in stdout.split("\n") if ('https' in x)])
    logger.debug(f"Found {len(conda_set)} conda package(s) in environment: {env_name}")


    # generate the explicit lock file and load it
    explicit_files = generate_explicit_lock_files(config)
    explicit_lock_file = config['paths']['explicit_lockfile']

    with open(explicit_lock_file, 'r') as f:
        lock_contents = f.read()
    lock_set = set([x for x in lock_contents.split("\n") if ('https' in x)])

    if conda_set == lock_set:
        logger.debug("Conda packages in environment and lock file are in sync.\n")
    else:
        check = False
        logger.warning('The lock file and environment are not in sync')
        in_env = conda_set.difference(lock_set)
        in_lock = lock_set.difference(conda_set)
        if len(in_env) > 0:
            logger.debug("\nThe following packages are in the environment but not in the lock file:\n")
            logger.debug("\n".join(in_env))
            logger.debug("\n")
            logger.info("To restore the environment to the state of the lock file")
            logger.info(">>> conda deactivate")
            logger.info(">>> conda ops env regenerate")
            logger.info(f">>> conda activate {env_name}")
            #logger.info(">>> conda ops sync")
        if len(in_lock) > 0:
            logger.debug("\nThe following packages are in the lock file but not in the environment:\n")
            logger.debug("\n".join(in_lock))
            logger.debug("\n")
            logger.info("To add these packages to the environment:")
            logger.info(">>> conda ops env install")
            #logger.info(">>> conda ops sync")

    # check that the pip contents of the lockfile match the conda environment

    # need to use a subprocess to ensure we get all of the pip package info
    conda_args = ["-n", env_name, '--json']
    result = subprocess.run(['conda', 'list'] + conda_args, capture_output=True)
    result_code = result.returncode
    stdout = result.stdout
    stderr = result.stderr
    conda_args = ["-n", env_name, "--json"]
    if result_code != 0:
        logger.error("Could not get packages from the environment")
        logger.info(stdout)
        logger.info(stderr)
        if die_on_error:
            sys.exit(result_code)
        else:
            return False
    conda_list = json.loads(stdout)

    conda_dict = {}
    for package in conda_list:
        if package['channel'] == 'pypi':
            conda_dict[package['name']] = package['version']

    logger.debug(f"Found {len(conda_dict)} pip package(s) in environment: {env_name}")

    if len(explicit_files) > 1:
        env_pip_interop(env_name=env_name, flag=True)

        logger.info("Checking consistency of pip installed packages...")
        logger.debug("Note that we only compare the package name and version number as this is all conda list gives us")
        lock_dict = {}
        lockfile = config['paths']['lockfile']
        with open(lockfile, 'r') as f:
            lock_list = json.load(f)
        for package in lock_list:
            if package['channel'] == 'pypi':
                lock_dict[package['name']] = package['version']

        if conda_dict == lock_dict:
            logger.debug("Pip packages in environment and lock file are in sync.\n")
        else:
            check = False
            # Find differing packages
            in_env = set(conda_dict.keys()).difference(lock_dict.keys())
            in_lock = set(lock_dict.keys()).difference(conda_dict.keys())
            if len(in_env) > 0:
                logger.debug("\nThe following packages are in the environment but not in the lock file:\n")
                logger.debug(", ".join(in_env))
                logger.debug("\n")
                logger.info("To restore the environment to the state of the lock file")
                logger.info(">>> conda deactivate")
                logger.info(">>> conda ops env regenerate")
                logger.info(f">>> conda activate {env_name}")
                #logger.info(">>> conda ops sync")
            if len(in_lock) > 0:
                logger.debug("\nThe following packages are in the lock file but not in the environment:\n")
                logger.debug(", ".join(in_lock))
                logger.debug("\n")
                logger.info("To add these packages to the environment:")
                logger.info(">>> conda ops env install")
                #logger.info(">>> conda ops sync")
            # Find differing versions
            differing_versions = {key: (conda_dict[key], lock_dict[key]) for key in conda_dict if key in lock_dict and conda_dict[key] != lock_dict[key]}
            if len(differing_versions) > 0:
                logger.debug("\nThe following package versions don't match:\n")
                logger.debug("\n".join([f"{x}: Lock version {lock_dict[x]}, Env version {conda_dict[x]}" for x in differing_versions]))
                logger.debug("\n")
                logger.info("To sync these versions:")
                logger.info(">>> conda ops env regenerate")
    elif len(conda_dict) > 0:
        check = False
        in_env = conda_dict.keys()
        logger.debug("\nThe following packages are in the environment but not in the lock file:\n")
        logger.debug(", ".join(in_env))
        logger.debug("\n")
        logger.info("To restore the environment to the state of the lock file")
        logger.info(">>> conda deactivate")
        logger.info(">>> conda ops env regenerate")
        logger.info(f">>> conda activate {env_name}")
        #logger.info(">>> conda ops sync")
    else:
        logger.debug("Pip packages in environment and lock file are in sync.\n")


    if die_on_error and not check:
        sys.exit(1)
    return check

def env_install(config=None):
    """
    Install the lockfile contents into the environment.

    This is *only* additive and does not delete existing packages form the environment.
    """
    if config is None:
        config = proj_load()

    env_name = config['settings']['env_name']
    explicit_lock_file = config['paths']['explicit_lockfile']
    explicit_files = generate_explicit_lock_files(config)

    logger.info(f"Installing lockfile into the environment {env_name}")
    conda_args = ["-n", env_name, "--file", str(explicit_lock_file)]
    stdout, stderr, result_code = run_command("install", conda_args, use_exception_handler=True)
    if result_code != 0:
        logger.info(stdout)
        logger.info(stderr)
        sys.exit(result_code)
    logger.info(stdout)

    pip_lock_file = config['paths']['pip_explicit_lockfile']
    if pip_lock_file in explicit_files:
        # Workaround for the issue in conda version 23.5.0 (and greater?) see issues.
        # We need to capture the pip install output to get the exact filenames of the packages
        stdout_backup  = sys.stdout
        sys.stdout = capture_output = StringIO()
        with redirect_stdout(capture_output):
            conda_args = ["-n", env_name, "pip", "install", "-r", str(pip_lock_file), "--verbose"]
            stdout, stderr, result_code = run_command("run", conda_args, use_exception_handler=True)
            if result_code != 0:
                logger.info(stdout)
                logger.info(stderr)
                return None
        sys.stdout = stdout_backup
        stdout_str = capture_output.getvalue()
        logger.info(stdout_str)


def env_delete(config=None, env_name=None):
    """
    Deleted the conda ops managed conda environment (aka. conda remove -n env_name --all)
    """
    if env_name is None:
        env_name = config['settings']['env_name']

    env_exists = check_env_exists(env_name)
    if not env_exists:
        logger.warning(f"The conda environment {env_name} does not exist, and cannot be deleted.")
        logger.info("To create the environment:")
        logger.info(">>> conda ops env create")
        #logger.info(">>> conda ops create")
    if check_env_active(env_name):
        logger.warning(f"The conda environment {env_name} is active, and cannot be deleted.")
        logger.info("To deactivate the environment:")
        logger.info(">>> conda deactivate")
    else:
        print(f"Deleting the conda environment {env_name}")
        stdout, stderr, result_code = run_command("remove", '-n', env_name, '--all', use_exception_handler=True)
        if result_code != 0:
            logger.info(stdout)
            logger.info(stderr)
            sys.exit(result_code)
        logger.info("Environment deleted.")

def env_regenerate(config=None, env_name=None, lock_file=None):
    """
    Delete the environment and regenerate from a lock file.
    """
    if lock_file is None:
        lock_file = config['paths']['lockfile']
    if env_name is None:
        env_name = config['settings']['env_name']

    if check_env_active(env_name):
        logger.error(f"The environment {env_name} to be regenerated is active. Deactivate and try again.")
        logger.info(">>> conda deactivate")
        sys.exit(1)

    env_delete(config=config, env_name=env_name)
    env_create(config=config, env_name=env_name, lock_file=lock_file)

############################################
#
# Helper Functions
#
############################################


def consistency_check(config=None, die_on_error=False):
    """
    Check the consistency of the requirements file vs. lock file vs. conda environment
    """
    proj_consistent = proj_check(config, die_on_error=True) # needed to continue
    logger.info("Configuration is consistent")

    env_name = config['settings']['env_name']
    logger.info(f"Managed Conda Environment: {env_name}")

    explicit_lock_file = config['paths']['explicit_lockfile']
    lock_file = config['paths']['lockfile']

    reqs_consistent = reqs_check(config, die_on_error=die_on_error)
    lockfile_consistent = lockfile_check(config, die_on_error=die_on_error)

    lockfile_reqs_consistent = lockfile_reqs_check(config, reqs_consistent=reqs_consistent, lockfile_consistent=lockfile_consistent, die_on_error=die_on_error)

    env_consistent = env_check(config, die_on_error=die_on_error)
    env_lockfile_consistent = env_lockfile_check(config, env_consistent=env_consistent, lockfile_consistent=lockfile_consistent, die_on_error=die_on_error)


def get_conda_info():
    """Get conda configuration information.

    This currently peeks into the conda internals.
    XXX Should this maybe be a conda info API call instead?
    XXX previous get_info_dict, but this does not contain the envs
    """
    stdout, stderr, result_code = run_command('info', '--json', use_exception_handler=True)
    if result_code != 0:
        logger.info(stdout)
        logger.info(stderr)
        sys.exit(result_code)
    return json.loads(stdout)


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
        logger.info(">>> conda ops proj create")
        #logger.info(">>> conda ops init")
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

def json_to_explicit(json_list, package_manager='conda'):
    """
    Convert a json lockfile to the explicit string format that
    can be used for create and update conda environments.
    """
    explicit_str = ''
    for package in json_list:
        '''
        # From old version of lock file
        # can also use the json['actions']['FETCH'] section when entries exist
        for extension in ['.conda', '.tar.bz2']:
            # in the future, update the lockfile format to include the md5 and extension information so it
            # does not have to get generated here
            package_url = '/'.join([package['base_url'], package['platform'], (package['dist_name'] + extension)]).strip()
            try:
                ret = urllib.request.urlopen(package_url).status
            except:
                ret = None
                logger.debug(package_url)
            if ret == 200:
                break
        if ret != 200:
            logger.error(f"Cannot find an appropriate URL for package {package} to create an explicit entry. Please make sure you have the internet accessible.")
            logger.error("Unimplemented: Update the lockfile.json at the time of generation to get extensions and md5 entries")
            sys.exit(1)
        '''
        if package['manager'] == 'conda' == package_manager:
            explicit_str += package['url']+'\n'
        if package['manager'] == 'pip' == package_manager:
            explicit_str += ' '.join([package['name'], '@', package['url'], f"--hash=sha256:{package['sha256']}"])+'\n'
    return explicit_str


def generate_explicit_lock_files(config=None, lock_file=None):
    """
    Generate an explicit lock files from the usual one (aka. of the format generated by `conda list --explicit`
    for conda and `package_name @ URL --hash=sha256:hash_value` for pip
    """
    logger.debug('Creating explicit lock file(s)')
    if lock_file is None:
        lock_file = config['paths']['lockfile']

    with open(lock_file, 'r') as f:
        json_reqs = json.load(f)

    # conda lock file
    explicit_str = "# This file may be used to create an environment using:\n# $ conda create --name <env> --file <this file>\n@EXPLICIT\n"
    explicit_str += json_to_explicit(json_reqs, package_manager='conda')

    explicit_lock_file = config['paths']['explicit_lockfile']
    with open(explicit_lock_file, 'w') as f:
        f.write(explicit_str)

    # pypi lock file
    pip_reqs = json_to_explicit(json_reqs, package_manager='pip')
    if len(pip_reqs) > 0:
        pip_lock_file = config['paths']['pip_explicit_lockfile']
        with open(pip_lock_file, 'w') as f:
            f.write(pip_reqs)
        return [explicit_lock_file, pip_lock_file]
    else:
        return [explicit_lock_file]


def check_env_exists(env_name):
    """
    Given the name of a conda environment, check if it exists
    """
    json_output = get_conda_info()

    env_list = [Path(x).name for x in json_output['envs']]
    if env_name in env_list:
        return True
    else:
        return False

def check_env_active(env_name):
    """
    Given the name of a conda environment, check if it is active
    """
    conda_info = get_conda_info()
    active_env = conda_info['active_prefix_name']

    if active_env == env_name:
        return True
    else:
        return False

def get_pypi_package_info(package_name, version, filename):
    """
    Get the pypi package information from pypi for a package name.

    If installed, use the matching distribution and platform information from what is installed.
    """
    url = f"https://pypi.org/pypi/{package_name}/{version}/json"

    # Fetch the package metadata JSON
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
    except Exception as e:
        print(e)
        logger.error(f"No releases found for url {url}")
        return None, None


    # Find the wheel file in the list of distributions
    releases = data["urls"]

    matching_releases = []
    for release in releases:
        if release['filename'] == filename:
            matching_releases.append(release)

    if matching_releases:
        for release in matching_releases:
            sha256_hash = release["digests"]["sha256"]
            url = release["url"]
            logger.debug(f"   The url for the file {filename} of {package_name} {version} is: {url}")
    else:
        logger.debug(f"No wheel distribution found for {package_name} {version}.")
        return None, None
    return url, sha256_hash

def extract_pip_installed_filenames(stdout, config=None):
    """
    Take the output of pip install --verbose to get the package name, version and filenames of what was installed.
    """
    pattern_1 = "Collecting "
    pattern_2 = "Requirement already satisfied: "
    list_stdout = re.split(r"Collecting |Requirement already ", stdout)

    filename_dict = {}
    for package_stdout in list_stdout[1:]:
        if "Using pip" in package_stdout:
            pass
        if "Using cached" in package_stdout:
            pattern = r'^(\S+)'
            match = re.search(pattern, package_stdout, re.MULTILINE)
            if match:
                requirement = Requirement(match.group(1))
                package_name = requirement.name
            else:
                package_name = None
                logger.error("No match for package_name found.")

            pattern = r'Using cached ([^\s]+)'
            match = re.search(pattern, package_stdout)
            if match:
                filename = match.group(1)
            else:
                filename = None
                logger.error("No match for filename found.")
            if filename is not None:
                version = filename.split('-')[1]
            else:
                version = None
            if version is not None:
                url, sha = get_pypi_package_info(package_name, version, filename)
            else:
                url = None
                sha = None
            filename_dict[package_name] = {'version': version, 'filename': filename, 'url': url, 'sha256':sha}
        elif "satisfied: " in package_stdout:
            # in this case, look in existing lockfile for details
            pattern = r'satisfied: ([^\s]+)'
            match = re.search(pattern, package_stdout)
            if match:
                requirement = Requirement(match.group(1))
                package_name = requirement.name
            else:
                package_name = None
                logger.error("No match for package_name found.")
            lockfile = config['paths']['lockfile']
            with open(lockfile, 'r') as lf:
                lock_list = json.load(lf)
            for package in lock_list:
                if package['name'] == package_name:
                    filename_dict[package_name] = {'version': package.get('version', None),
                                                   'filename': package.get('filename', None),
                                                   'url': package.get('url', None),
                                                   'sha256': package.get('sha256', None)}
                    break
        elif "Downloading" in package_stdout:
            pattern = r'^(\S+)'
            match = re.search(pattern, package_stdout, re.MULTILINE)
            if match:
                requirement = Requirement(match.group(1))
                package_name = requirement.name
            else:
                package_name = None
                logger.error("No match for package_name found.")

            pattern = r'Downloading ([^\s]+)'
            match = re.search(pattern, package_stdout)
            if match:
                filename = match.group(1)
            else:
                filename = None
                logger.error("No match for filename found.")
            if filename is not None:
                version = filename.split('-')[1]
            else:
                version = None
            if version is not None:
                url, sha = get_pypi_package_info(package_name, version, filename)
            else:
                url = None
                sha = None
            filename_dict[package_name] = {'version': version, 'filename': filename, 'url': url, 'sha256':sha}
        else:
            logger.error("Unimplemented so far...")
            logger.debug(package_stdout)
    return filename_dict


def conda_step_env_lock(channel, config, env_name=None):
    """
    Given a conda channel from the channel order list, update the environment and generate a new lock file.
    """
    if env_name is None:
        env_name = config['settings']['env_name']
    ops_dir = config['paths']['ops_dir']

    logger.info(f'Generating the intermediate lock file for channel {channel} via environment {env_name}')

    with open(ops_dir / f'.ops.{channel}-environment.txt') as f:
        package_list = f.read().split()

    if len(package_list) == 0:
        logger.warning("No packages to be installed at this step")
        return {}
    if check_env_exists(env_name):
        conda_args = ["-n", env_name, "-c", channel] + package_list
        stdout, stderr, result_code = run_command("install", conda_args, use_exception_handler=True)
        if result_code != 0:
            logger.info(stdout)
            logger.info(stderr)
            return None
    else:
        # create the environment directly
        conda_args = ["-n", env_name, "-c", channel] + package_list
        stdout, stderr, result_code = run_command("create", conda_args, use_exception_handler=True)
        if result_code != 0:
            logger.info(stdout)
            logger.info(stderr)
            return None

    channel_lockfile = (ops_dir / f'.ops.lock.{channel}')
    json_reqs = env_lock(lock_file=channel_lockfile, env_name=env_name)

    return json_reqs

def pip_step_env_lock(config, env_name=None):
    # set the pip interop flag to True as soon as pip packages are to be installed so conda remain aware of it
    # possibly set this at the first creation of the environment so it's always True

    if env_name is None:
        env_name = config['settings']['env_name']

    env_pip_interop(env_name=env_name, flag=True)

    ops_dir = config['paths']['ops_dir']
    logger.info(f'Generating the intermediate lock file for pip via environment {env_name}')

    pypi_reqs_file = ops_dir / f'.ops.pypi-requirements.txt'
    with open(pypi_reqs_file) as f:
        pypi_list = f.read().split('\n')

    # Workaround for the issue in cconda version 23.5.0 (and greater?) see issues.
    # We need to capture the pip install output to get the exact filenames of the packages
    stdout_backup  = sys.stdout
    sys.stdout = capture_output = StringIO()
    with redirect_stdout(capture_output):
        conda_args = ["-n", env_name, "pip", "install", "-r", str(pypi_reqs_file), "--verbose"]
        stdout, stderr, result_code = run_command("run", conda_args, use_exception_handler=True)
        if result_code != 0:
            logger.info(stdout)
            logger.info(stderr)
            return None
    sys.stdout = stdout_backup
    stdout_str = capture_output.getvalue()

    pip_dict = extract_pip_installed_filenames(stdout_str, config=config)

    channel_lockfile = (ops_dir / f'.ops.lock.pip')
    json_reqs = env_lock(lock_file=channel_lockfile, env_name=env_name, pip_dict=pip_dict)

    with open(ops_dir / f'.ops.sdist-requirements.txt') as f:
        sdist_list = f.read().split('\n')
    logger.error(f'TODO: Implement the pip step for sdists and editable modules {sdist_list}')

    return json_reqs

def env_pip_interop(config=None, env_name=None, flag=True):
    """
    Set the flag pip_interop_enabled to the value of flag locally for the conda ops managed env_activate
    """
    if env_name is None:
        env_name = config['settings']['env_name']

    if not check_env_exists(env_name):
        logger.error(f"Cannot set pip_interop_enabled flag locally in environment {env_name} as it does not exist.")
        logger.info(">>> conda ops env create")
        sys.exit(1)

    conda_info = get_conda_info()
    for env_path in conda_info['envs']:
        if Path(env_path).name == env_name:
            break

    condarc_path = Path(env_path) / '.condarc'
    conda_args = ["--set", 'pip_interop_enabled', str(flag), '--file', str(condarc_path)]

    stdout, stderr, result_code = run_command("config", conda_args, use_exception_handler=True)
    if result_code != 0:
        logger.info(stdout)
        logger.info(stderr)
        sys.exit(1)
    return True
