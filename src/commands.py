## Main Functionality

from pathlib import Path
import sys
import configparser
import json

CONDA_OPS_DIR_NAME = '.conda-ops'
STATUS_FILENAME = 'status.txt'
CONFIG_FILENAME = 'config.ini'
REQUIREMENTS_FILENAME = 'requirements'
LOCK_FILENAME = 'lockfile'



def ops_init():
    '''
    Initialize the conda ops project by creating a .conda-ops directory including the conda-ops project structure
    '''

    conda_ops_path = Path(f'./{CONDA_OPS_DIR_NAME}')

    if conda_ops_path.exists():
        print("conda ops has already been initialized")
        if input("Would you like to reinitialize (this will overwrite the existing config)? (y/n) ").lower() != 'y':
            sys.exit()
        # eventually, reinitialize from the new templates as with git init with no overwriting
    else:
        conda_ops_path.mkdir()

    print('Initializing conda ops...')

    # setup initial config
    config_file = conda_ops_path / CONFIG_FILENAME
    config = configparser.ConfigParser()
    env_name = Path.cwd().name
    config['DEFAULT'] = {'ENV_NAME': env_name}
    with open(config_file, 'w') as f:
        config.write(f)

    # create basic requirements file
    requirements_file = conda_ops_path / REQUIREMENTS_FILENAME
    requirements_dict = {'env_name': env_name, 'dependencies': ['python', 'pip']}
    with open(requirements_file, 'w') as f:
        json.dump(requirements_dict, f)
    print(f'Initialized conda-ops project in {conda_ops_path.resolve()}')

def ops_create():
    '''
    Create the first lockfile and environment
    '''
    print('TODO: check if the environment already exists...')

    ops_dir = find_conda_ops_dir()

    print('generating the lock file')
    lock_file = ops_dir / LOCK_FILENAME # we may not want this until we create the first environment
    lock_file.touch()

    config = configparser.ConfigParser()
    config.read(ops_dir / CONFIG_FILENAME)
    env_name = config['DEFAULT']['ENV_NAME']
    print(f'creating the environment {env_name}')

    status_file = ops_dir / STATUS_FILENAME
    with open(status_file, 'w') as f:
        f.write(f"Environment {env_name} created.")
    print(f'Environment created. Activate the environment using `conda activate {env_name}` to begin.')


######################
#
# Helper Functions
#
######################

def consistency_check():
    ops_dir = find_conda_ops_dir()
    print('checking consistency of the requirements, lock file, and environment...')
    config = configparser.ConfigParser()
    config.read(ops_dir / CONFIG_FILENAME)
    env_name = config['DEFAULT']['ENV_NAME']
    print(env_name)
    status_file = ops_dir / STATUS_FILENAME
    requirements_file = ops_dir / REQUIREMENTS_FILENAME
    lock_file = ops_dir / LOCK_FILENAME

    print('check if requirements file is newer than the lock file')
    print('check if the lock file has packages not in the environment')
    print('check if the environment has packages not in the lock file')

def find_conda_ops_dir():
    '''
    Helper function to locate a conda ops directory in the current or parent directories.
    '''
    ops_dir = find_upwards(Path.cwd(), CONDA_OPS_DIR_NAME)
    if ops_dir is None:
        print('Fatal: Not a conda ops project (or any of the parent directories). To create a conda ops project run `conda ops init`')
        sys.exit()
    else:
        return ops_dir

def find_upwards(cwd, filename):
    """
    Search in the current directory and all directories above it
    for a filename or directory of a particular name.

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
