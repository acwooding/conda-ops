# tests/test_reqs.py

from pathlib import Path
import os
import subprocess
import sys

import pytest

from conda_ops.commands_reqs import reqs_add, reqs_remove, reqs_create, reqs_check, pop_pip_section, check_package_in_list, clean_package_args, open_file_in_editor
from conda_ops.requirements import is_url_requirement
from conda_ops.utils import yaml


CONDA_OPS_DIR_NAME = ".conda-ops"


def test_reqs_create(shared_temp_dir):
    """
    Test the reqs_create function.
    We will call reqs_create and then check if the requirements file was correctly created.
    """
    config = {
        "paths": {"requirements": shared_temp_dir / CONDA_OPS_DIR_NAME / "reqs_test_environment.yml"},
        "settings": {"env_name": str(shared_temp_dir.name)},
    }
    ops_dir = shared_temp_dir / CONDA_OPS_DIR_NAME
    ops_dir.mkdir(exist_ok=True)
    reqs_create(config)
    assert config["paths"]["requirements"].exists()


def test_reqs_add(setup_config_files):
    """
    Test the reqs_add function.
    We will create a temporary requirements file, add some packages and
    then check if these packages were correctly added.
    """
    config = setup_config_files
    reqs_add(["black", "flake8", "-e .", "git+https://my-url.com"], config=config)
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert "black" in reqs["dependencies"]
    assert "flake8" in reqs["dependencies"]
    assert "-e ." not in reqs["dependencies"]
    assert "git+https://my-url.com" not in reqs["dependencies"]


def test_reqs_remove(setup_config_files):
    """
    Test the reqs_remove function.
    We will create a temporary requirements file, add some packages, remove one,
    and then check if the correct package was removed.
    """
    config = setup_config_files
    reqs_add(["black", "flake8"], config=config)
    reqs_remove(["black"], config=config)
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert "black" not in reqs["dependencies"]
    assert "flake8" in reqs["dependencies"]


def test_reqs_add_pip(setup_config_files):
    """
    Test the reqs_add function for the pip channel.
    We will create a requirements file, add a package from the pip channel,
    and then check if the package was correctly added.
    """
    config = setup_config_files
    reqs_add(["flask", "git+https://github.com/lmcinnes/pynndescent.git", "-e ."], channel="pip", config=config)
    reqs = yaml.load(config["paths"]["requirements"].open())
    conda_reqs, pip_dict = pop_pip_section(reqs["dependencies"])
    assert "flask" not in conda_reqs
    assert "flask" in pip_dict["pip"]
    assert "git+https://github.com/lmcinnes/pynndescent.git" in pip_dict["pip"]
    assert "-e ." in pip_dict["pip"]


def test_reqs_remove_pip(setup_config_files):
    """
    Test the reqs_remove function for the pip channel.
    We will create a requirements file, add a package from the pip channel,
    remove it, and then check if the package was correctly removed.
    """
    config = setup_config_files
    reqs_add(["flask", "git+https://github.com/lmcinnes/pynndescent.git", "-e ."], channel="pip", config=config)
    reqs_remove(["flask", "git+https://github.com/lmcinnes/pynndescent.git", "-e ."], config=config)
    reqs = yaml.load(config["paths"]["requirements"].open())
    conda_reqs, pip_dict = pop_pip_section(reqs["dependencies"])

    assert pip_dict is None


def test_reqs_add_conda_forge(setup_config_files):
    """
    Test the reqs_add function for the conda-forge channel.
    We will create a requirements file, add a package from the conda-forge channel,
    and then check if the package was correctly added.
    """
    config = setup_config_files
    reqs_add(["pylint"], channel="conda-forge", config=config)
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert "conda-forge::pylint" in reqs["dependencies"]
    assert "conda-forge" in reqs["channel-order"]


def test_reqs_remove_conda_forge(setup_config_files):
    """
    Test the reqs_remove function for the conda-forge channel.
    We will create a temporary requirements file, add a package from the conda-forge channel,
    remove it, and then check if the package was correctly removed.
    """
    config = setup_config_files
    reqs_file = config["paths"]["requirements"]
    reqs_add(["pylint"], channel="conda-forge", config=config)
    reqs_remove(["pylint"], config=config)
    reqs = yaml.load(reqs_file.open())
    assert "conda-forge::pylint" not in reqs["dependencies"]
    assert "conda-forge" not in reqs["channel-order"]


def test_reqs_add_version(setup_config_files):
    """
    Test the reqs_add function.
    We will create a temporary requirements file, add a package, and add a version pin of that package.
    """
    config = setup_config_files
    reqs_add(["black"], config=config)
    reqs_add(["black>22"], config=config)
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert "black" not in reqs["dependencies"]
    assert "black[version='>22']" in reqs["dependencies"]


def test_reqs_remove_version(setup_config_files):
    """
    Test the reqs_add function.
    We will create a temporary requirements file, add a package, and add a version pin of that package.
    """
    config = setup_config_files
    reqs_add(["black>22"], config=config)
    reqs_remove(["black"], config=config)
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert "black[version='>22']" not in reqs["dependencies"]


def test_check_package_in_list():
    # Test case 1: Matching package found
    package_list = ["numpy", "requests", "numpy==1.18.5", "torch", "numpy==1.18.6"]
    matching_packages = check_package_in_list("numpy", package_list)
    assert matching_packages == ["numpy", "numpy==1.18.5", "numpy==1.18.6"]

    # Test case 2: No matching package found
    package_list = ["pandas", "matplotlib", "tensorflow", "scipy"]
    matching_packages = check_package_in_list("numpy", package_list)
    assert matching_packages == []

    # Test case 3: Matching package with channel specifier
    package_list = ["pandas", "conda-forge::numpy", "conda-forge::numpy==1.19.2"]
    matching_packages = check_package_in_list("numpy", package_list)
    assert matching_packages == ["conda-forge::numpy", "conda-forge::numpy==1.19.2"]

    # Test case 4: Matching package with different version specifier
    package_list = ["numpy==1.18.3", "numpy>=1.18.0", "numpy<2.0.0"]
    matching_packages = check_package_in_list("numpy==1.18.5", package_list)
    assert matching_packages == ["numpy==1.18.3", "numpy>=1.18.0", "numpy<2.0.0"]


def test_reqs_add_equals_conda(setup_config_files):
    """
    Test the reqs_add function.
    We will create a temporary requirements file, add a package, and add a version pin of that package
    with an equals sign.
    """
    config = setup_config_files
    reqs_add(["black=22"], config=config)
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert "black=22" in reqs["dependencies"]
    assert "black==22" not in reqs["dependencies"]


def test_reqs_add_equals_pip(setup_config_files):
    """
    Test the reqs_add function.
    We will create a temporary requirements file, add a package, and add a version pin of that package
    with an equals sign.
    """
    config = setup_config_files
    reqs_add(["black=22"], config=config, channel="pip")
    reqs = yaml.load(config["paths"]["requirements"].open())
    conda_reqs, pip_dict = pop_pip_section(reqs["dependencies"])

    assert "black==22" not in conda_reqs
    assert "black==22" in pip_dict["pip"]
    assert "black=22" not in conda_reqs
    assert "black=22" not in pip_dict["pip"]


def test_reqs_check(setup_config_files):
    """
    Test the reqs_check function.
    We will create a requirements file and then check the requirements are in the correct format.
    """
    config = setup_config_files
    assert reqs_check(config)


def test_reqs_check_add_manual_equals_conda(setup_config_files):
    """
    Test the reqs_check function when packages have been added manually.
    We will create a temporary requirements file, add a package, and add a version pin of that package
    with an equals sign. Check that the duplicate package is noticed.

    This is in the conda section, not the pip section.
    """
    config = setup_config_files

    # add dependencies directly to file
    reqs = yaml.load(config["paths"]["requirements"].open())
    reqs["dependencies"] += ["python=3.11", "python"]

    with open(config["paths"]["requirements"], "w") as f:
        yaml.dump(reqs, f)

    with pytest.raises(SystemExit):
        reqs_check(config)


def test_reqs_check_add_manual_equals_pip(setup_config_files):
    """
    Test the reqs_check function when packages have been added manually.
    We will create a temporary requirements file, add a package, and add a version pin of that package
    with an equals sign. Check that the duplicate package is noticed.

    This is in the pip section, not the conda section.
    """
    config = setup_config_files

    # add dependencies directly to file
    reqs = yaml.load(config["paths"]["requirements"].open())
    pip_dict = {"pip": ["python=3.11"]}
    reqs["dependencies"] += [pip_dict]

    with open(config["paths"]["requirements"], "w") as f:
        yaml.dump(reqs, f)

    with pytest.raises(SystemExit):
        reqs_check(config)


def test_reqs_check_add_manual_invalid_package_str(setup_config_files):
    """
    Test the reqs_check function when packages have been added manually.
    We will create a temporary requirements file, add a package manually that is ill-specified.
    """
    config = setup_config_files

    # add dependencies directly to file
    reqs = yaml.load(config["paths"]["requirements"].open())
    reqs["dependencies"].append("titan>?3.11")

    with open(config["paths"]["requirements"], "w") as f:
        yaml.dump(reqs, f)

    # reqs_check should fail
    with pytest.raises(SystemExit):
        reqs_check(config)
    assert reqs_check(config, die_on_error=False) is False


def test_clean_package_args():
    """
    Test that package_args works as expected.
    """
    test_paths = ["-e .", "/my/file/path", "git+https://my/url"]
    assert clean_package_args(test_paths, channel="pip") == test_paths

    # test different channels
    for channel in ["pip", "conda-forge", None]:
        # valid list to be altered
        package_args = ["numpy pandas", "black=22 ", " python=3.11"]

        clean_packages = clean_package_args(package_args, channel=channel)
        if channel == "pip":
            assert clean_packages == sorted(["python==3.11", "numpy", "pandas", "black==22"])
        else:
            assert clean_packages == sorted(["python=3.11", "numpy", "pandas", "black=22"])

        # two copies of python. This should fail.
        package_args = ["python", "python=3.11"]
        with pytest.raises(SystemExit):
            clean_package_args(package_args, channel=channel)

        # invalid spec to fail on
        package_args = ["python >?3.11"]
        with pytest.raises(SystemExit):
            clean_package_args(package_args)


def test_open_file_in_editor_mac_linux(mocker, capsys):
    """
    Test opening a file in the default editor on macOS and Linux.

    It should use the editor specified by the 'EDITOR' environment variable.
    """
    mocker.patch("subprocess.run")
    mocker.patch.dict(os.environ, {"EDITOR": "nano"})
    filename = "test.txt"
    open_file_in_editor(filename)
    path = Path(filename).resolve()
    subprocess.run.assert_called_with(["nano", path], check=True)


def test_open_file_in_editor_mac_linux_default(mocker, capsys):
    """
    Test opening a file in the default editor on macOS and Linux with no 'EDITOR' environment variable.

    It should fall back to using the 'vim' editor.
    """
    mocker.patch("subprocess.run")
    mocker.patch.dict(os.environ, clear=True)
    filename = "test.txt"
    open_file_in_editor(filename)
    path = Path(filename).resolve()
    subprocess.run.assert_called_with(["vim", path], check=True)


def test_open_file_in_editor_mac_linux_with_visual(mocker, capsys):
    """
    Test opening a file in the default editor on macOS and Linux using the 'VISUAL' environment variable.

    It should use the editor specified by the 'VISUAL' environment variable when 'EDITOR' is not set.
    """
    mocker.patch("subprocess.run")
    mocker.patch.dict(os.environ, clear=True)
    mocker.patch.dict(os.environ, {"VISUAL": "mg"})
    filename = "test.txt"
    open_file_in_editor(filename)
    path = Path(filename).resolve()
    subprocess.run.assert_called_with(["mg", path], check=True)


def test_open_file_in_editor_windows(mocker, capsys):
    """
    Test opening a file in the default editor on Windows.

    It should use the editor specified by the 'EDITOR' environment variable.
    """
    mocker.patch("subprocess.run")
    mocker.patch.dict(os.environ, {"EDITOR": "notepad++"})
    filename = "test.txt"
    mocker.patch.object(sys, "platform", "win32")
    open_file_in_editor(filename)
    path = Path(filename).resolve()
    subprocess.run.assert_called_with(["notepad++", path], check=True)


def test_open_file_in_editor_windows_default(mocker, capsys):
    """
    Test opening a file in the default editor on Windows with no 'EDITOR' environment variable.

    It should fall back to using the 'notepad.exe' editor.
    """
    mocker.patch("subprocess.run")
    mocker.patch.dict(os.environ, clear=True)
    filename = "test.txt"
    mocker.patch.object(sys, "platform", "win32")
    open_file_in_editor(filename)
    path = Path(filename).resolve()
    subprocess.run.assert_called_with(["notepad", path], check=True)


def test_open_file_in_editor_unsupported_platform(mocker, caplog):
    """
    Test opening a file on an unsupported platform.

    It should display a message indicating that the platform is unsupported.
    """
    mocker.patch("subprocess.run")
    mocker.patch.object(sys, "platform", "sunos")
    filename = "test.txt"
    open_file_in_editor(filename)
    assert "Unsupported platform" in caplog.text


def test_is_url_requirement_standard_requirements():
    requirements = ["requests", "numpy==1.18.5"]

    for requirement in requirements:
        assert not is_url_requirement(requirement)


def test_is_url_requirement_path_requirements():
    requirements = ["../my-package", "~/projects/other-package", ".", ".."]

    for requirement in requirements:
        assert is_url_requirement(requirement)
