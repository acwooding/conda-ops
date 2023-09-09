import pytest
from pathlib import Path
from conda_ops.utils import yaml
from conda_ops.conda_config import condarc_create

CONDA_OPS_DIR_NAME = ".conda-ops"


@pytest.fixture(scope="session")
def shared_temp_dir(tmp_path_factory):
    # Create the temporary directory
    temp_dir = tmp_path_factory.mktemp("condaops_temp_dir")

    print(temp_dir)

    # Yield the temporary directory path to the tests
    yield Path(temp_dir)


@pytest.fixture(scope="function")
def setup_config_files(shared_temp_dir):
    ops_dir = shared_temp_dir / CONDA_OPS_DIR_NAME
    config = {
        "paths": {
            "ops_dir": ops_dir,
            "requirements": ops_dir / "environment.yml",
            "lockfile": ops_dir / "lockfile.json",
            "explicit_lockfile": ops_dir / "lockfile.explicit",
            "pip_explicit_lockfile": ops_dir / "lockfile.pypi",
            "nohash_explicit_lockfile": ops_dir / "lockfile.nohash",
            "condarc": ops_dir / ".condarc",
        },
        "settings": {
            "env_name": str(shared_temp_dir.name),
        },
    }
    requirements_dict = {
        "name": str(shared_temp_dir.name),
        "channels": ["defaults"],
        "channel-order": ["defaults"],
        "dependencies": ["python", "pip"],
    }

    ops_dir.mkdir(exist_ok=True)
    with open(config["paths"]["requirements"], "w") as f:
        yaml.dump(requirements_dict, f)

    condarc_create(config=config)

    return config


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    # Check if any tests failed
    shared_temp_dir = session.config.cache.get("shared_temp_dir", None)
    keep_temp = getattr(shared_temp_dir, "keep_temp", False)

    if session.testsfailed > 0:
        # Give the boilerplate to keep the temp dir if needed
        keep_temp = False
    if (not keep_temp) and (shared_temp_dir is not None):
        shared_temp_dir.rmdir()


def pytest_collection_modifyitems(config, items):
    """
    Modify the order of test collection.

    This hook is called by pytest to modify the order of test collection.

    It makes sure the test named "test_proj_create" is moved to the beginning
    of the test collection.

    Args:
        config: pytest config object.
        items: List of test items to be collected.

    """
    test_proj_create = None

    for item in items:
        if item.name == "test_proj_create":
            test_proj_create = item
            break

    if test_proj_create:
        items.remove(test_proj_create)
        items.insert(0, test_proj_create)
