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
