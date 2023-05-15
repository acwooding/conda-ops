## Main Functionality

from pathlib import Path
import sys
import configparser

CONDA_OPS_DIR_NAME = '.conda-ops'
STATUS_FILENAME = 'status.txt'
CONFIG_FILENAME = 'config.ini'
REQUIREMENTS_FILENAME = 'requirements'
LOCK_FILENAME = 'lockfile'



def ops_init():
    '''
    Initialize the conda ops project by creating a .conda-ops directory including the conda-ops project structure
    '''
    print('checking if conda ops is already initialized...')

    conda_ops_path = Path(f'./{CONDA_OPS_DIR_NAME}')

    if conda_ops_path.exists():
        print('conda ops is already initialized...for now, there is nothing more to do')
        # eventually, reinitialize from the new templates as with git init
    else:
        print('Initializing conda ops')
        conda_ops_path.mkdir()

        # setup initial config
        config_file = conda_ops_path / CONFIG_FILENAME
        config = configparser.ConfigParser()
        config['DEFAULT'] = {'ENV_NAME': Path.cwd().name}
        with open(config_file, 'w') as f:
            config.write(f)

        # create other files
        status_file = conda_ops_path / STATUS_FILENAME
        requirements_file = conda_ops_path / REQUIREMENTS_FILENAME
        lock_file = conda_ops_path / LOCK_FILENAME # we may not want this until we create the first environment
        for filename in [status_file, requirements_file, lock_file]:
            filename.touch()
        print(f'Initialized conda-ops project in {conda_ops_path.resolve()}')



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
