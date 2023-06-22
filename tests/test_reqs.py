# tests/test_reqs.py

from src.commands import reqs_add, reqs_remove, reqs_create, reqs_check, check_package_in_list, clean_package_args
from src.commands import yaml, pop_pip_section
import pytest

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
    reqs_add(["black", "flake8"], config=config)
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert "black" in reqs["dependencies"]
    assert "flake8" in reqs["dependencies"]


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
    reqs_add(["flask"], channel="pip", config=config)
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert {"pip": ["flask"]} in reqs["dependencies"]


def test_reqs_remove_pip(setup_config_files):
    """
    Test the reqs_remove function for the pip channel.
    We will create a requirements file, add a package from the pip channel,
    remove it, and then check if the package was correctly removed.
    """
    config = setup_config_files
    reqs_add(["flask"], channel="pip", config=config)
    reqs_remove(["flask"], config=config)
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert {"pip": ["flask"]} not in reqs["dependencies"]


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


def test_reqs_add_equals(setup_config_files):
    """
    Test the reqs_add function.
    We will create a temporary requirements file, add a package, and add a version pin of that package
    with an equals sign.
    """
    config = setup_config_files
    reqs_add(["black=22"], config=config)
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert "black=22" not in reqs["dependencies"]
    assert "black==22" in reqs["dependencies"]


def test_reqs_add_equals(setup_config_files):
    """
    Test the reqs_add function.
    We will create a temporary requirements file, add a package, and add a version pin of that package
    with an equals sign.
    """
    config = setup_config_files
    reqs_add(["black=22"], config=config)
    reqs = yaml.load(config["paths"]["requirements"].open())
    assert "black=22" not in reqs["dependencies"]
    assert "black==22" in reqs["dependencies"]


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


def test_reqs_check_add_manual_invalid_package_str(setup_config_files):
    """
    Test the reqs_check function when packages have been added manually.
    We will create a temporary requirements file, add a package manually that is ill-specified.
    """
    config = setup_config_files

    # add dependencies directly to file
    reqs = yaml.load(config["paths"]["requirements"].open())
    reqs["dependencies"].append("titan>?3.11")
    print(reqs)
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
    # test different channels
    for channel in ["pip", "conda-forge", None]:
        # valid list to be altered
        package_args = ["numpy pandas", "black=22 ", " python=3.11"]

        clean_packages = clean_package_args(package_args, channel=channel)
        assert clean_packages == sorted(["python==3.11", "numpy", "pandas", "black==22"])

        # two copies of python. This should fail.
        package_args = ["python", "python=3.11"]
        with pytest.raises(SystemExit):
            clean_package_args(package_args, channel=channel)

        # invalid spec to fail on
        package_args = ["python >?3.11"]
        with pytest.raises(SystemExit):
            clean_package_args(package_args)
