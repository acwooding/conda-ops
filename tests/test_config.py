from pytest_mock import mocker
from pathlib import Path
import sys

from conda.common.serialize import yaml_round_trip_load

from conda_ops.conda_config import check_config_items_match, CONDAOPS_OPINIONS, condarc_create, WHITELIST_CHANNEL, WHITELIST_SOLVER, condaops_config_manage
from conda_ops.utils import logger


def test_check_config_items_match():
    assert check_config_items_match()


def test_check_config_items_match_mocked(mocker):
    mocker.patch("conda_ops.conda_config.WHITELIST_CHANNEL", ["param1", "param2"])
    mocker.patch("conda_ops.conda_config.WHITELIST_SOLVER", ["param3", "param4"])
    mocker.patch("conda_ops.conda_config.CONFIG_LIST", ["param5", "param6"])
    mocker.patch.object(logger, "warning")

    config_map = {"Channel Configuration": ["param1", "param2"], "Solver Configuration": ["param3", "param4"], "Other Category": ["param5", "param6"]}

    # Invoke the function
    result = check_config_items_match(config_map)

    # Assert the expected outcome
    assert result is True
    logger.warning.assert_not_called()


def test_check_config_items_match_channel_mismatch(mocker):
    mocker.patch.object(logger, "warning")

    mocker.patch("conda_ops.conda_config.WHITELIST_CHANNEL", ["param1", "param2"])
    mocker.patch("conda_ops.conda_config.WHITELIST_SOLVER", ["param3", "param4"])
    mocker.patch("conda_ops.conda_config.CONFIG_LIST", ["param5", "param6"])

    config_map = {"Channel Configuration": ["param1", "param2", "extra_param"], "Solver Configuration": ["param3", "param4"], "Other Category": ["param5", "param6"]}

    result = check_config_items_match(config_map)

    assert result is False
    logger.warning.assert_called_with("The following channel configurations are in conda but not being tracked: ['extra_param']")


def test_check_config_items_match_solver_mismatch(mocker):
    mocker.patch.object(logger, "warning")

    mocker.patch("conda_ops.conda_config.WHITELIST_CHANNEL", ["param1", "param2"])
    mocker.patch("conda_ops.conda_config.WHITELIST_SOLVER", ["param3", "param4"])
    mocker.patch("conda_ops.conda_config.CONFIG_LIST", ["param5", "param6"])

    config_map = {"Channel Configuration": ["param1", "param2"], "Solver Configuration": ["param3", "param4", "extra_param"], "Other Category": ["param5", "param6"]}

    result = check_config_items_match(config_map)

    assert result is False
    logger.warning.assert_called_with("The following solver configurations are in conda but not being tracked: ['extra_param']")


def test_check_config_items_match_total_mismatch(mocker):
    mocker.patch.object(logger, "warning")

    mocker.patch("conda_ops.conda_config.WHITELIST_CHANNEL", ["param1", "param2"])
    mocker.patch("conda_ops.conda_config.WHITELIST_SOLVER", ["param3", "param4"])
    mocker.patch("conda_ops.conda_config.CONFIG_LIST", ["param5", "param6"])

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


def test_condaops_config_manage_show(mocker, setup_config_files):
    argv = ["config", "--show"]
    args = mocker.Mock(
        command="config",
        show=[],
        show_sources=False,
        validate=False,
        describe=None,
        get=None,
        append=[],
        prepend=[],
        set=[],
        remove=[],
    )
    config = setup_config_files
    mocker.patch.object(sys, "exit")

    condaops_config_manage(argv, args, config)

    sys.exit.assert_not_called()


def test_condaops_config_manage_show_sources(mocker, setup_config_files):
    argv = ["config", "--show-sources"]
    args = mocker.Mock(
        command="config",
        show=None,
        show_sources=True,
        validate=False,
        describe=None,
        get=None,
        append=[],
        prepend=[],
        set=[],
        remove=[],
    )
    config = setup_config_files
    mocker.patch.object(sys, "exit")

    condaops_config_manage(argv, args, config)

    sys.exit.assert_not_called()


def test_condaops_config_manage_validate(mocker, setup_config_files):
    argv = ["config", "--validate"]
    args = mocker.Mock(
        command="config",
        show=None,
        show_sources=False,
        validate=True,
        describe=None,
        get=None,
        append=[],
        prepend=[],
        set=[],
        remove=[],
    )
    config = setup_config_files
    mocker.patch.object(sys, "exit")

    condaops_config_manage(argv, args, config)

    sys.exit.assert_not_called()


def test_condaops_config_manage_describe(mocker, setup_config_files):
    argv = ["config", "--describe"]
    args = mocker.Mock(
        command="config",
        show=None,
        show_sources=False,
        validate=False,
        describe=[],
        get=None,
        append=[],
        prepend=[],
        set=[],
        remove=[],
    )
    config = setup_config_files
    mocker.patch.object(sys, "exit")

    condaops_config_manage(argv, args, config)

    sys.exit.assert_not_called()


def test_condaops_config_manage_get(mocker, setup_config_files):
    argv = ["config", "--get", "param1", "param2"]
    args = mocker.Mock(get=["param1", "param2"], command="config", show=None, show_sources=False, validate=False, describe=None, append=[], prepend=[], set=[], remove=[])
    config = setup_config_files

    mocker.patch.object(sys, "exit")

    condaops_config_manage(argv, args, config)

    sys.exit.assert_not_called()


def test_condaops_config_manage_append(mocker, setup_config_files):
    argv = ["config", "--append", "key1", "value1"]
    args = mocker.Mock(append=[("key1", "value1")], command="config", show=None, show_sources=False, validate=False, describe=None, get=None, prepend=[], set=[], remove=[])
    config = setup_config_files
    mocker.patch.object(sys, "exit")

    condaops_config_manage(argv, args, config)

    # should remove the values from the list and not call run_command
    sys.exit.assert_not_called()


def test_condaops_config_manage_prepend(mocker, setup_config_files):
    argv = ["config", "--prepend", "key1", "value1"]
    args = mocker.Mock(command="config", show=None, show_sources=False, validate=False, describe=None, get=None, append=[], set=[], remove=[], prepend=[("key1", "value1")])
    config = setup_config_files
    mocker.patch.object(sys, "exit")

    condaops_config_manage(argv, args, config)

    # should remove the values from the list and not call run_command
    sys.exit.assert_not_called()


def test_condaops_config_manage_set(mocker, setup_config_files):
    argv = ["config", "--set", "key1", "value1"]
    args = mocker.Mock(command="config", show=None, show_sources=False, validate=False, describe=None, get=None, append=[], prepend=[], remove=[], set=[("key1", "value1")])
    config = setup_config_files
    mocker.patch.object(sys, "exit")

    condaops_config_manage(argv, args, config)

    # should remove the values from the list and not call run_command
    sys.exit.assert_not_called()


def test_condaops_config_manage_remove(mocker, setup_config_files):
    argv = ["config", "--remove", "param2", "value2"]
    args = mocker.Mock(command="config", show=None, show_sources=False, validate=False, describe=None, get=None, append=[], prepend=[], set=[], remove=[("param2", "value2")])
    config = setup_config_files
    mocker.patch.object(sys, "exit")

    condaops_config_manage(argv, args, config)

    # should remove the values from the list and not call run_command
    sys.exit.assert_not_called()
