from src.utils import logger
from conda.base.context import context


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
