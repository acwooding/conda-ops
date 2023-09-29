# Import the function or method you want to test
import subprocess

from conda_ops.utils import yaml
from conda_ops.commands import consistency_check


def test_conda_ops_add(setup_config_structure, shared_temp_dir):
    config = setup_config_structure

    argv = ["conda", "ops", "add", "black", "flake8"]

    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=shared_temp_dir, text=True)

    print(result.stdout)
    print(result.stderr)

    assert result.returncode == 0
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert "black" in reqs["dependencies"]
    assert "flake8" in reqs["dependencies"]


def test_conda_ops_remove(setup_config_structure, shared_temp_dir):
    config = setup_config_structure

    argv = ["conda", "ops", "remove", "black", "flake8"]

    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=shared_temp_dir, text=True)

    print(result.stdout)
    print(result.stderr)

    assert result.returncode == 0
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert "black" not in reqs["dependencies"]
    assert "flake8" not in reqs["dependencies"]


def test_conda_ops_sync(setup_config_structure, shared_temp_dir):
    config = setup_config_structure

    argv = ["conda", "ops", "sync", "-f"]

    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=shared_temp_dir, text=True)

    print(result.stdout)
    print(result.stderr)

    assert result.returncode == 0

    assert consistency_check(config)


def test_conda_ops_install(setup_config_structure, shared_temp_dir):
    config = setup_config_structure

    argv = ["conda", "ops", "install", "black", "flake8"]

    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=shared_temp_dir, text=True)

    print(result.stdout)
    print(result.stderr)

    assert result.returncode == 0
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert "black" in reqs["dependencies"]
    assert "flake8" in reqs["dependencies"]


def test_conda_ops_uninstall(setup_config_structure, shared_temp_dir):
    config = setup_config_structure

    argv = ["conda", "ops", "uninstall", "black", "flake8"]

    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=shared_temp_dir, text=True)

    print(result.stdout)
    print(result.stderr)

    assert result.returncode == 0
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert "black" not in reqs["dependencies"]
    assert "flake8" not in reqs["dependencies"]

    assert consistency_check(config)
