# tests/test_reqs.py

from src.commands import reqs_add, reqs_remove, reqs_create, reqs_check
from src.commands import yaml
import pytest

def test_reqs_add(shared_temp_dir):
    """
    Test the reqs_add function.
    We will create a temporary requirements file, add some packages and
    then check if these packages were correctly added.
    """
    config = {
        'paths': {'requirements': shared_temp_dir / 'reqs_test_environment.yml'},
        'settings': {'env_name': str(shared_temp_dir)}
    }
    reqs_create(config)
    reqs_add(['black', 'flake8'], config=config)
    reqs = yaml.load(config['paths']['requirements'].open())
    assert 'black' in reqs['dependencies']
    assert 'flake8' in reqs['dependencies']

def test_reqs_remove(shared_temp_dir):
    """
    Test the reqs_remove function.
    We will create a temporary requirements file, add some packages, remove one,
    and then check if the correct package was removed.
    """
    config = {
        'paths': {'requirements': shared_temp_dir / 'reqs_test_environment.yml'},
        'settings': {'env_name': str(shared_temp_dir)}
    }
    reqs_create(config)
    reqs_add(['black', 'flake8'], config=config)
    reqs_remove(['black'], config=config)
    reqs = yaml.load(config['paths']['requirements'].open())
    assert 'black' not in reqs['dependencies']
    assert 'flake8' in reqs['dependencies']

def test_reqs_create(shared_temp_dir):
    """
    Test the reqs_create function.
    We will call reqs_create and then check if the requirements file was correctly created.
    """
    config = {
        'paths': {'requirements': shared_temp_dir / 'reqs_test_environment.yml'},
        'settings': {'env_name': str(shared_temp_dir)}
    }
    reqs_create(config)
    assert config['paths']['requirements'].exists()

def test_reqs_check(shared_temp_dir):
    """
    Test the reqs_check function.
    We will create a requirements file and then check the requirements are in the correct format.
    """
    config = {
        'paths': {'requirements': shared_temp_dir / 'reqs_test_environment.yml'},
        'settings': {'env_name': str(shared_temp_dir)}
    }
    reqs_create(config)
    assert reqs_check(config)

def test_reqs_add_pip(shared_temp_dir):
    """
    Test the reqs_add function for the pip channel.
    We will create a requirements file, add a package from the pip channel,
    and then check if the package was correctly added.
    """
    config = {
        'paths': {'requirements': shared_temp_dir / 'reqs_test_environment.yml'},
        'settings': {'env_name': str(shared_temp_dir)}
    }
    reqs_create(config)
    reqs_add(['flask'], channel='pip', config=config)
    reqs = yaml.load(config['paths']['requirements'].open())
    assert {'pip': ['flask']} in reqs['dependencies']

def test_reqs_remove_pip(shared_temp_dir):
    """
    Test the reqs_remove function for the pip channel.
    We will create a requirements file, add a package from the pip channel,
    remove it, and then check if the package was correctly removed.
    """
    config = {
        'paths': {'requirements': shared_temp_dir / 'reqs_test_environment.yml'},
        'settings': {'env_name': str(shared_temp_dir)}
    }
    reqs_create(config)
    reqs_add(['flask'], channel='pip', config=config)
    reqs_remove(['flask'], config=config)
    reqs = yaml.load(config['paths']['requirements'].open())
    assert {'pip': ['flask']} not in reqs['dependencies']

def test_reqs_add_conda_forge(shared_temp_dir):
    """
    Test the reqs_add function for the conda-forge channel.
    We will create a requirements file, add a package from the conda-forge channel,
    and then check if the package was correctly added.
    """
    config = {
        'paths': {'requirements': shared_temp_dir / 'reqs_test_environment.yml'},
        'settings': {'env_name': str(shared_temp_dir)}
    }
    reqs_create(config)
    reqs_add(['pylint'], channel='conda-forge', config=config)
    reqs = yaml.load(config['paths']['requirements'].open())
    assert 'conda-forge::pylint' in reqs['dependencies']
    assert 'conda-forge' in reqs['channel-order']

def test_reqs_remove_conda_forge(shared_temp_dir):
    """
    Test the reqs_remove function for the conda-forge channel.
    We will create a temporary requirements file, add a package from the conda-forge channel,
    remove it, and then check if the package was correctly removed.
    """
    config = {
        'paths': {'requirements': shared_temp_dir / 'reqs_test_environment.yml'},
        'settings': {'env_name': str(shared_temp_dir)}
    }
    # make sure no previous file exists
    reqs_file = config['paths']['requirements']
    if reqs_file.exists():
        reqs_file.unlink()

    reqs_create(config)
    reqs_add(['pylint'], channel='conda-forge', config=config)
    reqs_remove(['pylint'], config=config)
    reqs = yaml.load(reqs_file.open())
    assert 'conda-forge::pylint' not in reqs['dependencies']
    assert 'conda-forge' not in reqs['channel-order']
