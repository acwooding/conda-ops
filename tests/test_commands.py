# Import the function or method you want to test
import subprocess

from conda_ops.utils import yaml
from conda_ops.commands import consistency_check
from conda_ops.commands_reqs import pop_pip_section


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


def test_conda_ops_add_parsing(setup_config_structure, shared_temp_dir):
    config = setup_config_structure

    test_cases = ["-c conda_forge pkg1 pkg2 defaults::pkg3", "--pip pkg1 -e pkg2", "-c chan1 pkg1 pkg2 -c chan2 pkg3 pkg4 --pip pkg5 pkg6 -e pkg7 -epkg8 pkg9 defaults::p10"]

    result_cases = [
        {"conda": ["conda_forge::pkg1", "conda_forge::pkg2", "pkg3"]},
        {"pip": ["pkg1", "-e pkg2"]},
        {"conda": ["chan1::pkg1", "chan1::pkg2", "chan2::pkg3", "chan2::pkg4", "pkg9", "p10"], "pip": ["pkg5", "pkg6", "-e pkg7", "-e pkg8"]},
    ]

    for i, test in enumerate(test_cases):
        argv = ["conda", "ops", "add"] + test.split()
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=shared_temp_dir, text=True)
        assert result.returncode == 0
        reqs = yaml.load(config["paths"]["requirements"].open())
        conda_reqs, pip_dict = pop_pip_section(reqs["dependencies"])
        result = result_cases[i]

        for package in result.get("conda", []):
            assert package in conda_reqs
        for package in result.get("pip", []):
            if pip_dict is not None:
                assert package in pip_dict.get("pip", None)

    # cleanup
    config["paths"]["requirements"].unlink()


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

    argv = ["conda", "ops", "uninstall", "black", "flake8", "-f"]

    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=shared_temp_dir, text=True)

    print(result.stdout)
    print(result.stderr)

    assert result.returncode == 0
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert "black" not in reqs["dependencies"]
    assert "flake8" not in reqs["dependencies"]

    assert consistency_check(config)
