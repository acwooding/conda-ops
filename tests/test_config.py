from src.conda_config import check_config_items_match
from src.utils import logger
from pytest_mock import mocker


def test_check_config_items_match():
    assert check_config_items_match()


def test_check_config_items_match_mocked(mocker):
    mocker.patch("src.conda_config.WHITELIST_CHANNEL", ["param1", "param2"])
    mocker.patch("src.conda_config.WHITELIST_SOLVER", ["param3", "param4"])
    mocker.patch("src.conda_config.CONFIG_LIST", ["param5", "param6"])
    mocker.patch.object(logger, "warning")

    config_map = {"Channel Configuration": ["param1", "param2"], "Solver Configuration": ["param3", "param4"], "Other Category": ["param5", "param6"]}

    # Invoke the function
    result = check_config_items_match(config_map)

    # Assert the expected outcome
    assert result is True
    logger.warning.assert_not_called()


def test_check_config_items_match_channel_mismatch(mocker):
    mocker.patch.object(logger, "warning")

    mocker.patch("src.conda_config.WHITELIST_CHANNEL", ["param1", "param2"])
    mocker.patch("src.conda_config.WHITELIST_SOLVER", ["param3", "param4"])
    mocker.patch("src.conda_config.CONFIG_LIST", ["param5", "param6"])

    config_map = {"Channel Configuration": ["param1", "param2", "extra_param"], "Solver Configuration": ["param3", "param4"], "Other Category": ["param5", "param6"]}

    result = check_config_items_match(config_map)

    assert result is False
    logger.warning.assert_called_with("The following channel configurations are in conda but not being tracked: ['extra_param']")


def test_check_config_items_match_solver_mismatch(mocker):
    mocker.patch.object(logger, "warning")

    mocker.patch("src.conda_config.WHITELIST_CHANNEL", ["param1", "param2"])
    mocker.patch("src.conda_config.WHITELIST_SOLVER", ["param3", "param4"])
    mocker.patch("src.conda_config.CONFIG_LIST", ["param5", "param6"])

    config_map = {"Channel Configuration": ["param1", "param2"], "Solver Configuration": ["param3", "param4", "extra_param"], "Other Category": ["param5", "param6"]}

    result = check_config_items_match(config_map)

    assert result is False
    logger.warning.assert_called_with("The following solver configurations are in conda but not being tracked: ['extra_param']")


def test_check_config_items_match_total_mismatch(mocker):
    mocker.patch.object(logger, "warning")

    mocker.patch("src.conda_config.WHITELIST_CHANNEL", ["param1", "param2"])
    mocker.patch("src.conda_config.WHITELIST_SOLVER", ["param3", "param4"])
    mocker.patch("src.conda_config.CONFIG_LIST", ["param5", "param6"])

    config_map = {"Channel Configuration": ["param1", "param2"], "Solver Configuration": ["param3", "param4"], "Other Category": ["param5", "param6", "extra_param"]}

    result = check_config_items_match(config_map)

    assert result is False
    logger.warning.assert_called_with("The following configurations are in conda but unrecognized by conda-ops: ['extra_param']")
