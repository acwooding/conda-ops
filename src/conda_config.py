from collections.abc import Mapping
import sys

from conda.base.context import context
from conda.common.serialize import yaml_round_trip_load, yaml_round_trip_dump
from conda.common.iterators import groupby_to_dict as groupby
from conda.common.compat import isiterable

from .utils import logger
from .python_api import run_command
from .commands_proj import CondaOpsManagedCondarc

##################################################################
#
# Config Settings
#
##################################################################


# the settings we have strong opinions about and will warn if they are set differently
CONDAOPS_OPINIONS = {
    "channels": ["defaults"],
    "channel_priority": "flexible",
    "override_channels_enabled": True,
    "pip_interop_enabled": True,  # we only insist on this once you have pip requirements in your requirements file
}

# channel config settings that we want to keep track of
WHITELIST_CHANNEL = [
    "add_anaconda_token",
    "allow_non_channel_urls",
    "allowlist_channels",
    "channel_alias",
    "channels",
    "custom_channels",
    "custom_multichannels",
    "default_channels",
    "experimental",
    "fetch_threads",
    "migrated_channel_aliases",
    "migrated_custom_channels",
    "override_channels_enabled",
    "repodata_fns",
    "repodata_threads",
    "restore_free_channel",
    "use_only_tar_bz2",
]

# solver config settings that we want to keep track of
WHITELIST_SOLVER = [
    "aggressive_update_packages",
    "auto_update_conda",
    "channel_priority",
    "create_default_packages",
    "disallowed_packages",
    "force_reinstall",
    "pinned_packages",
    "pip_interop_enabled",
    "solver",
    "track_features",
]

# config settings that we are aware of
CONFIG_LIST = [
    "add_anaconda_token",
    "add_pip_as_python_dependency",
    "aggressive_update_packages",
    "allow_conda_downgrades",
    "allow_cycles",
    "allow_non_channel_urls",
    "allow_softlinks",
    "allowlist_channels",
    "always_copy",
    "always_softlink",
    "always_yes",
    "anaconda_upload",
    "auto_activate_base",
    "auto_stack",
    "auto_update_conda",
    "bld_path",
    "changeps1",
    "channel_alias",
    "channel_priority",
    "channel_settings",
    "channels",
    "client_ssl_cert",
    "client_ssl_cert_key",
    "clobber",
    "conda_build",
    "create_default_packages",
    "croot",
    "custom_channels",
    "custom_multichannels",
    "debug",
    "default_channels",
    "default_python",
    "default_threads",
    "deps_modifier",
    "dev",
    "disallowed_packages",
    "download_only",
    "dry_run",
    "enable_private_envs",
    "env_prompt",
    "envs_dirs",
    "error_upload_url",
    "execute_threads",
    "experimental",
    "extra_safety_checks",
    "fetch_threads",
    "force",
    "force_32bit",
    "force_reinstall",
    "force_remove",
    "ignore_pinned",
    "json",
    "local_repodata_ttl",
    "migrated_channel_aliases",
    "migrated_custom_channels",
    "non_admin_enabled",
    "notify_outdated_conda",
    "number_channel_notices",
    "offline",
    "override_channels_enabled",
    "path_conflict",
    "pinned_packages",
    "pip_interop_enabled",
    "pkgs_dirs",
    "proxy_servers",
    "quiet",
    "remote_backoff_factor",
    "remote_connect_timeout_secs",
    "remote_max_retries",
    "remote_read_timeout_secs",
    "repodata_fns",
    "repodata_threads",
    "report_errors",
    "restore_free_channel",
    "rollback_enabled",
    "root_prefix",
    "safety_checks",
    "sat_solver",
    "separate_format_cache",
    "shortcuts",
    "show_channel_urls",
    "signing_metadata_url_base",
    "solver",
    "solver_ignore_timestamps",
    "ssl_verify",
    "subdir",
    "subdirs",
    "target_prefix_override",
    "track_features",
    "unsatisfiable_hints",
    "unsatisfiable_hints_check_depth",
    "update_modifier",
    "use_index_cache",
    "use_local",
    "use_only_tar_bz2",
    "verbosity",
    "verify_threads",
]


##################################################################
#
# Config Control Functions
#
##################################################################


def check_config_items_match(config_map=None):
    """
    Compare the built-in configuration lists with the conda configuration lists and determine if they match.

    config_map: Optionally pass a dict to make testing easier

    Returns: True if they all match and False if there is a difference between them.
    """
    if config_map is None:
        config_map = context.category_map

    # check the whitelist sections
    whitelist_categories = ["Channel Configuration", "Solver Configuration"]

    channel_match = sorted(WHITELIST_CHANNEL) == sorted(list(config_map["Channel Configuration"]))
    if not channel_match:
        conda_set = set(config_map["Channel Configuration"])
        ops_set = set(WHITELIST_CHANNEL)
        extra_conda = conda_set.difference(ops_set)
        extra_ops = ops_set.difference(conda_set)
        if len(extra_conda) > 0:
            logger.warning(f"The following channel configurations are in conda but not being tracked: {list(extra_conda)}")
        if len(extra_ops) > 0:
            logger.warning(f"The following channel configurations are missing from conda: {list(extra_ops)}")

    solver_match = sorted(WHITELIST_SOLVER) == sorted(list(config_map["Solver Configuration"]))
    if not solver_match:
        conda_set = set(config_map["Solver Configuration"])
        ops_set = set(WHITELIST_SOLVER)
        extra_conda = conda_set.difference(ops_set)
        extra_ops = ops_set.difference(conda_set)
        if len(extra_conda) > 0:
            logger.warning(f"The following solver configurations are in conda but not being tracked: {list(extra_conda)}")
        if len(extra_ops) > 0:
            logger.warning(f"The following solver configurations are missing from conda: {list(extra_ops)}")

    # check everything else
    config_list = set(CONFIG_LIST) - set(WHITELIST_CHANNEL + WHITELIST_SOLVER)
    total_config = []
    for category, parameter_names in config_map.items():
        if category not in whitelist_categories:
            total_config += parameter_names
    total_match = sorted(config_list) == sorted(total_config)
    if not total_match:
        conda_set = set(total_config)
        ops_set = set(config_list)
        extra_conda = conda_set.difference(ops_set)
        extra_ops = ops_set.difference(conda_set)
        if len(extra_conda) > 0:
            logger.warning(f"The following configurations are in conda but unrecognized by conda-ops: {list(extra_conda)}")
        if len(extra_ops) > 0:
            logger.warning(f"The following configurations settings are missing from conda: {list(extra_ops)}")
    return channel_match and solver_match and total_match


def check_condarc_matches_opinions(rc_path=None, config=None, die_on_error=True):
    """
    Check that the conda ops managed .condarc file matches the CONDAOPS_OPINIONS.
    """
    check = True
    if not rc_path:
        rc_path = config["paths"]["condarc"]
    elif not rc_path.exists():
        logger.error(f"The file {rc_path} does not exist. There is nothing to compare against.")
        logger.info("To create the managed .condarc file:")
        logger.info(">>> conda ops config create")
        check = False
    else:
        rc_config = yaml_round_trip_load(rc_path)
        for key, value in CONDAOPS_OPINIONS.items():
            if rc_config[key] != value:
                logger.warning(f"The .condarc value of the the parameter {key}, does not match the recommended conda ops setting of {value}. Unexpected behaviour is possible.")
                logger.info("To change to the recommended setting:")
                if key == "channels":
                    for vrc in rc_config[key]:
                        if vrc != value[0]:
                            logger.info(f">>> conda ops config --remove {key} {vrc}")
                    if "defaults" not in rc_config[key]:
                        logger.info(f">>> conda ops config --add {key} {value}")
                else:
                    logger.info(f">>> conda ops config --set {key} {value}")

    if die_on_error and not check:
        sys.exit(1)

    return check


def condarc_create(rc_path=None, config=None):
    """
    Generate a .condarc file consisting of the channel and solver configurations.

    Use the following settings even if it's different than what currently exists in the configuration:

    CONDAOPS_OPINIONS = {
        "channels": ["defaults"],
        "channel_priority": "flexible",
        "override_channels_enabled": True,
        "pip_interop_enabled": True,
    }

    Set all the rest of the channel and solver configurations to the current ones from the conda that is running.

    Create a .condarc file in rc_path if specified and in config['paths']['condarc'] if rc_path is not given.
    It will not overwrite the path if it exists.
    """
    if not rc_path:
        rc_path = config["paths"]["condarc"]
    if rc_path.exists():
        logger.error(f"The file {rc_path} already exists. Please remove it if you'd like to create a new one.")
        return False

    paramater_names = context.list_parameters()

    param_dict = {key: getattr(context, key) for key in paramater_names}

    grouped_paramaters = groupby(
        lambda p: context.describe_parameter(p)["parameter_type"],
        context.list_parameters(),
    )
    sequence_parameters = grouped_paramaters["sequence"]

    rc_config = {}
    for key in WHITELIST_CHANNEL + WHITELIST_SOLVER:
        if key in CONDAOPS_OPINIONS.keys():
            if key in sequence_parameters:
                if list(param_dict[key]) != CONDAOPS_OPINIONS[key]:
                    logger.warning(f"Setting conda-ops configuration of {key} to {CONDAOPS_OPINIONS[key]}, while existing default is {param_dict[key]}.")
            elif str(param_dict[key]) != str(CONDAOPS_OPINIONS[key]):
                logger.warning(f"Setting conda-ops configuration of {key} to {CONDAOPS_OPINIONS[key]}, while existing default is {param_dict[key]}.")
            rc_config[key] = CONDAOPS_OPINIONS[key]
        else:
            # Add in custom formatting
            # modifications as per conda/cli/main_config.py
            if key == "custom_channels":
                rc_config["custom_channels"] = {channel.name: f"{channel.scheme}://{channel.location}" for channel in param_dict["custom_channels"].values()}
            elif key == "custom_multichannels":
                rc_config["custom_multichannels"] = {multichannel_name: [str(x) for x in channels] for multichannel_name, channels in param_dict["custom_multichannels"].items()}
            elif key == "channel_alias":
                rc_config[key] = str(param_dict[key])
            elif isinstance(param_dict[key], Mapping):
                rc_config[key] = {str(k): str(v) for k, v in param_dict[key].items()}
            elif isiterable(param_dict[key]):
                rc_config[key] = [str(x) for x in param_dict[key]]
            elif isinstance(param_dict[key], bool) or param_dict[key] is None:
                if key == "repodata_threads":
                    rc_config[key] = 0
                else:
                    rc_config[key] = param_dict[key]
            else:
                rc_config[key] = str(param_dict[key])

    with open(rc_path, "w") as rc:
        rc.write(yaml_round_trip_dump(rc_config))

    logger.debug("Created .condarc file")
    return True


def env_pip_interop(config=None, flag=True):
    """
    Set the flag pip_interop_enabled to the value of flag locally for the conda ops managed environment
    """
    condarc_path = config["paths"]["condarc"]
    conda_args = ["--set", "pip_interop_enabled", str(flag), "--file", str(condarc_path)]

    stdout, stderr, result_code = run_command("config", conda_args, use_exception_handler=True)
    if result_code != 0:
        logger.error(stdout)
        logger.error(stderr)
        sys.exit(1)
    return True


def condaops_config_manage(argv: list, args, config=None):
    """
    Allow for modifications of the conda-ops managed .condarc file using same arguments to conda config
    as conda config. Only modify and track parameters in the WHITELISTs.

    If an attempt is made to modify a parameter *not* on the WHITELIST, error out and suggest using conda config
    directly.

    Supports:
    * show
    * show_sources
    * validate
    * describe

    * get
    * append
    * prepend, add
    * set
    * remove
    """
    WHITELIST = WHITELIST_CHANNEL + WHITELIST_SOLVER
    # grab arguments directly as it is easier to pass on that way
    argv.remove(str(args.command))
    file_args = ["--file", str(config["paths"]["condarc"])]

    if args.show is not None:
        print("\n")
        print(yaml_round_trip_dump(yaml_round_trip_load(config["paths"]["condarc"])))
        print("\n")
    if args.show_sources or args.validate:
        # fall through directly, but add $CONDARC to make sure we use the condaops settings
        conda_args = argv + file_args
        with CondaOpsManagedCondarc(config["paths"]["condarc"]):
            stdout, stderr, result_code = run_command("config", conda_args)
            if result_code != 0:
                logger.error(stdout)
                logger.error(stderr)
                sys.exit(result_code)
            else:
                if args.validate:
                    logger.info("Conda config validated")
                if args.show_sources:
                    print(stdout)
    if args.describe is not None:
        # describe the parameters listed. shows default conda values. Default to
        # describing the parameters in the WHITELIST if no args given.
        if args.describe:
            describe_args = args.describe
        else:
            describe_args = WHITELIST
        stdout, stderr, result_code = run_command("config", "--describe", *describe_args)
        if result_code != 0:
            logger.error(stdout)
            logger.error(stderr)
            sys.exit(result_code)
        print("\n")
        print(stdout)
        print(stderr)
    if args.get is not None:
        # get the config values of the parameters listed. default to WHITELIST if no args given.
        # only checks for values in the conda ops managed list.
        if args.get:
            get_args = args.get
        else:
            get_args = WHITELIST
        stdout, stderr, result_code = run_command("config", "--get", *get_args, *file_args)
        if result_code != 0:
            logger.error(stdout)
            logger.error(stderr)
            sys.exit(result_code)
        print(stdout)
        print(stderr)
    if args.append or args.prepend or args.set or args.remove:
        # check that the keys are in the WHITELIST and then pass to conda to edit the .condarc file
        # prepend, append, add
        not_in_whitelist = []
        if args.append or args.prepend:
            for arg in (args.prepend, args.append):
                for key, item in arg:
                    key, _ = key.split(".", 1) if "." in key else (key, None)
                    if key not in WHITELIST:
                        index_key = argv.index(key)
                        if argv[index_key - 1] in ["--append", "--prepend"]:
                            del argv[index_key - 1 : index_key + 2]
                        else:
                            logger.error("Something is wrong here with the parameters being passed:")
                            logger.error(argv)
                        not_in_whitelist.append(key)
        if args.set or args.remove:
            if args.set:
                arg = args.set
            if args.remove:
                arg = args.remove
            for key, item in arg:
                key, subkey = key.split(".", 1) if "." in key else (key, None)
                if key not in WHITELIST:
                    index_key = argv.index(key)
                    if argv[index_key - 1] in ["--set", "--remove"]:
                        del argv[index_key - 1 : index_key + 2]
                    else:
                        logger.error("Something is wrong here with the parameters being passed:")
                        logger.error(argv)
                    not_in_whitelist.append(key)
        if len(argv) > 0:
            stdout, stderr, result_code = run_command("config", *(argv + file_args))
            if result_code != 0:
                logger.error(stdout)
                logger.error(stderr)
                sys.exit(result_code)
            print(stdout)
        if len(not_in_whitelist) > 0:
            gap = "\n- "
            print("The following parameters are not recognized in the conda ops managed config:\n" f"- {gap.join(not_in_whitelist)}")
            print("To manage them use `conda config` instead.")
