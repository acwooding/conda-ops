import pytest
import tempfile
from pathlib import Path

@pytest.fixture(scope="session")
def shared_temp_dir(tmp_path_factory):
    # Create the temporary directory
    temp_dir = tmp_path_factory.mktemp("condaops_temp_dir")

    print(temp_dir)

    # Yield the temporary directory path to the tests
    yield Path(temp_dir)

@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    # Check if any tests failed
    if session.testsfailed > 0:
        # Give the boilerplate to keep the temp dir if needed
        session.config.cache.set("keep_temp_dir", False)

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
