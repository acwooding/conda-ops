from pytest_mock import mocker
from pathlib import Path

from conda.common.serialize import yaml_round_trip_load

from src.conda_config import check_config_items_match, CONDAOPS_OPINIONS, condarc_create, WHITELIST_CHANNEL, WHITELIST_SOLVER
from src.utils import logger


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


def test_condarc_create(setup_config_files):
    """
    Check that the opinionated entries match the generated file and that only whitelist parameters are included in the file.
    """
    config = setup_config_files
    rc_path = Path(str(config["paths"]["condarc"]) + "test")
    condarc_create(rc_path=rc_path)
    with open(rc_path, "r") as fh:
        rc_config = yaml_round_trip_load(fh)
    WHITELIST = WHITELIST_CHANNEL + WHITELIST_SOLVER
    assert len(rc_config) == len(WHITELIST)
    for key in rc_config.keys():
        assert key in WHITELIST
    for key, value in CONDAOPS_OPINIONS.items():
        assert value == rc_config[key]
