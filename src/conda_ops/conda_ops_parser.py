import argparse
import conda.plugins

from .commands import consistency_check, lockfile_generate, sync
from .commands_proj import proj_load, proj_create
from .commands_reqs import reqs_create, reqs_add, reqs_remove, reqs_list, reqs_edit
from .commands_lockfile import lockfile_check, lockfile_reqs_check
from .commands_env import (
    env_activate,
    env_deactivate,
    env_regenerate,
    env_clean_temp,
    env_create,
    env_delete,
    env_check,
    env_lockfile_check,
    env_install,
    env_lock,
)
from .conda_config import condarc_create, condaops_config_manage, check_condarc_matches_opinions
from .utils import logger


def conda_ops(argv: list):
    argv = list(argv)
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", help="Set the log level")

    parser = argparse.ArgumentParser("conda ops", parents=[parent_parser])
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    init = configure_parser_init(subparsers, parents=[parent_parser])

    add = configure_parser_add(subparsers, parents=[parent_parser])
    remove = configure_parser_remove(subparsers, parents=[parent_parser])
    sync_parser = configure_parser_sync(subparsers, parents=[parent_parser])
    install = configure_parser_install(subparsers, parents=[parent_parser])
    uninstall = configure_parser_uninstall(subparsers, parents=[parent_parser])
    config_parser = configure_parser_config(subparsers, parents=[parent_parser])
    status = subparsers.add_parser("status", help="Report on the status of the conda-ops project")

    activate = subparsers.add_parser("activate", add_help=False)
    activate.add_argument("kind", nargs=argparse.REMAINDER)
    deactivate = subparsers.add_parser("deactivate", add_help=False)

    reqs = configure_parser_reqs(subparsers, parents=[parent_parser])
    lockfile = subparsers.add_parser("lockfile", help="Additional operations for managing the lockfile. Accepts generate, check, reqs-check.", parents=[parent_parser])
    lockfile.add_argument("kind", choices=["generate", "check", "reqs-check"])
    env = subparsers.add_parser("env", help="Additional operations for managing the environment. Accepts create, install, delete, regenerate, check, lockfile-check.", parents=[parent_parser])
    env.add_argument("kind", choices=["create", "delete", "activate", "deactivate", "check", "lockfile-check", "regenerate", "install", "clean"])
    env.add_argument("-n", "--name", dest="env_name", nargs=1, type=str)

    # hidden parser for testing purposes
    subparsers.add_parser("test")

    args = parser.parse_args(argv)

    logger.setLevel(args.log_level)

    if args.command not in ["init"]:
        config = proj_load(die_on_error=True)

    if args.command in ["status", None]:
        consistency_check(config=config)
    elif args.command == "config":
        if args.create:
            condarc_create(config=config)
        else:
            condaops_config_manage(argv, args, config=config)
    elif args.command == "init":
        config, overwrite = proj_create(prefix=args.relative_prefix)
        condarc_create(config=config, overwrite=overwrite)
        reqs_create(config=config)
    elif args.command == "add":
        packages = args.packages + args.other_packages
        reqs_add(packages, config=config)
        logger.info("To update the lockfile and environment with the additional packages:")
        logger.info(">>> conda ops sync")
    elif args.command == "remove":
        reqs_remove(args.packages, config=config)
        logger.info("To update the lockfile and environment with the removal of packages:")
        logger.info(">>> conda ops sync")
    elif args.command == "install":
        packages = args.packages + args.other_packages
        reqs_add(packages, config=config)
        sync_complete = sync(config, force=args.force)
        if sync_complete:
            logger.info("Packages installed.")
    elif args.command == "uninstall":
        reqs_remove(args.packages, config=config)
        sync_complete = sync(config, force=True)
        if sync_complete:
            logger.info("Packages uninstalled.")
    elif args.command == "sync":
        sync_complete = sync(config, force=args.force)
        if sync_complete:
            logger.info("Sync complete")
    elif args.command == "activate":
        env_activate(config=config)
    elif args.command == "deactivate":
        env_deactivate(config)
    elif args.command == "lockfile":
        if args.kind == "generate":
            lockfile_generate(config, regenerate=True)
        elif args.kind == "check":
            check, _ = lockfile_check(config)
            if check:
                logger.info("Lockfile is consistent")
        elif args.kind == "reqs-check":
            check = lockfile_reqs_check(config)
            if check:
                logger.info("Lockfile and requirements are consistent")
    elif args.command == "env":
        if args.kind == "create":
            env_create(config=config)
        if args.kind == "regenerate":
            env_regenerate(config=config)
        elif args.kind == "install":
            env_install(config=config)
        elif args.kind == "delete":
            success = env_delete(config=config)
            if success:
                logger.info("Conda ops environment deleted.")
        elif args.kind == "activate":
            env_activate(config=config)
        elif args.kind == "deactivate":
            env_deactivate(config)
        elif args.kind == "check":
            env_check(config=config)
        elif args.kind == "lockfile-check":
            env_lockfile_check(config=config)
        elif args.kind == "clean":
            if args.env_name is not None:
                env_clean_temp(env_base_name=args.env_name[0])
            else:
                env_clean_temp(config=config)
    elif args.command == "test":
        check_condarc_matches_opinions(config=config)
    elif args.reqs_command == "create":
        reqs_create(config)
    elif args.reqs_command == "add":
        reqs_add(args.packages, config=config)
        logger.info("To update the lock file:")
        logger.info(">>> conda ops sync")
    elif args.reqs_command == "remove":
        reqs_remove(args.packages, config=config)
        logger.info("To update the lock file:")
        logger.info(">>> conda ops sync")
    elif args.reqs_command == "check":
        check = reqs_check(config)
        if check:
            logger.info("Requirements file is consistent")
    elif args.reqs_command == "list":
        reqs_list(config)
    elif args.reqs_command == "edit":
        reqs_edit(config)
    else:
        logger.error(f"Unhandled conda ops subcommand: '{args.command}'")


# #############################################################################################
#
# custom actions
#
# #############################################################################################
class ParseChannels(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, const=None, default=None, type=None, choices=None, required=False, help=None, metavar=None):
        argparse.Action.__init__(
            self,
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar,
        )
        for name, value in sorted(locals().items()):
            if name == "self" or value is None:
                continue
        return

    def __call__(self, parser, namespace, values, option_string=None):
        return_values = getattr(namespace, self.dest)
        channel_name = values[0]

        n = 1
        if len(values) > n:
            for i, package in enumerate(values[n:]):
                # check if the channel is specified directly
                # this breaks the -c pattern and returns it to normal package
                # parsing
                if "::" in package:
                    return_values += values[i + n :]
                    break
                return_values.append(f"{channel_name}::{package}")
        setattr(namespace, self.dest, return_values)


class ParsePip(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, const=None, default=None, type=None, choices=None, required=False, help=None, metavar=None):
        argparse.Action.__init__(
            self,
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar,
        )
        for name, value in sorted(locals().items()):
            if name == "self" or value is None:
                continue
        return

    def __call__(self, parser, namespace, values, option_string=None):
        channel_name = "pip"
        return_values = getattr(namespace, self.dest)
        if len(values) > 0:
            for i, package in enumerate(values):
                # check if the channel is specified directly
                # as :: breaks the --pip pattern
                if "::" in package:
                    return_values += values[i + n :]
                    break
                elif "-e" in option_string:
                    return_values.append(f"-e {channel_name}::{package}")
                else:
                    return_values.append(f"{channel_name}::{package}")
        setattr(namespace, self.dest, return_values)


# #############################################################################################
#
# sub-parsers
#
# #############################################################################################


def configure_parser_add(subparsers, parents):
    descr = "Add packages to the requirements file."
    p = subparsers.add_parser("add", description=descr, help=descr, parents=parents)
    p.add_argument("packages", type=str, nargs="*", default=[], action="extend")
    p.add_argument(
        "-c",
        "--channel",
        nargs="+",
        dest="other_packages",
        default=[],
        action=ParseChannels,
        help="Indicates the channel that the added packages that follow are coming from, that is, `-c c1 p1 p2` indicates that packages p1 and p2 come from channel c1",
    )
    p.add_argument(
        "--pip",
        nargs="+",
        default=[],
        dest="other_packages",
        action=ParsePip,
        help="Indicates that the packages following it are from pip, that is, `--pip p1 p2` indicates that the pacakges p1 and p2 should be added to the pip section",
    )
    p.add_argument(
        "-e",
        nargs=1,
        default=[],
        dest="other_packages",
        action=ParsePip,
        help="Indicates that the package that follows should be installed via pip with the editable option, that is `-e p1` means that the package p1 should be installed by pip in editable mode",
    )
    return p


def configure_parser_init(subparsers, parents):
    descr = "Create a conda ops project in the current directory and create a requirements file if it doesn't exist."
    p = subparsers.add_parser("init", description=descr, help=descr, parents=parents)
    p.add_argument("-p", "--prefix", action="store", help="Path to environment location (i.e. prefix) relative to the .conda-ops/envs directory.", dest="relative_prefix", default="")
    return p


def configure_parser_install(subparsers, parents):
    descr = "Add packages to the requirements file and sync the environment and lockfile."
    p = subparsers.add_parser("install", description=descr, help=descr, parents=parents)
    p.add_argument("packages", type=str, nargs="*", default=[], action="extend")
    p.add_argument(
        "-c",
        "--channel",
        nargs="+",
        dest="other_packages",
        default=[],
        action=ParseChannels,
        help="Indicates the channel that the added packages that follow are coming from, that is, `-c c1 p1 p2` indicates that pacakges p1 and p2 come from channel c1",
    )
    p.add_argument(
        "--pip",
        nargs="+",
        default=[],
        action=ParsePip,
        dest="other_packages",
        help="Indicates that the packages following it are from pip, that is, `--pip p1 p2` indicates that the pacakges p1 and p2 should be added to the pip section",
    )
    p.add_argument(
        "-e",
        nargs=1,
        default=[],
        action=ParsePip,
        dest="other_packages",
        help="Indicates that the package that follows should be installed via pip with the editable option, that is `-e p1` means that the package p1 should be installed by pip in editable mode",
    )
    p.add_argument("-f", "--force", action="store_true", help="Force the lock file and environment to be recreated.")
    return p


def configure_parser_remove(subparsers, parents):
    descr = "Remove packages from the requirements file. Removes all versions of the packages from any channel they are found in."
    p = subparsers.add_parser("remove", description=descr, help=descr, parents=parents)
    p.add_argument("packages", type=str, nargs="+")
    return p


def configure_parser_sync(subparsers, parents):
    descr = "Sync the environment and lock file with the requirements file."
    p = subparsers.add_parser("sync", description=descr, help=descr, parents=parents)
    p.add_argument("-f", "--force", action="store_true", help="Force the lock file and environment to be recreated.")
    return p


def configure_parser_uninstall(subparsers, parents):
    descr = "Remove packages from the requirements file and sync the environment and lockfile. Removes all versions of the packages from any channel they are found in."
    p = subparsers.add_parser("uninstall", description=descr, help=descr, parents=parents)
    p.add_argument("packages", type=str, nargs="+")
    return p


def configure_parser_reqs(subparsers, parents):
    descr = "Additional operations for managing the requirements file. Accepts arguments create, add, remove, check, list, edit."
    p = subparsers.add_parser("reqs", help=descr, parents=parents)
    reqs_subparser = p.add_subparsers(dest="reqs_command", metavar="reqs_command")
    reqs_subparser.add_parser("create")
    r_add = configure_parser_add(reqs_subparser, parents)
    r_remove = reqs_subparser.add_parser("remove")
    r_remove.add_argument("packages", type=str, nargs="+")
    reqs_subparser.add_parser("check")
    reqs_subparser.add_parser("list")
    reqs_subparser.add_parser("edit")
    return p


def configure_parser_config(subparsers, parents):
    """
    Largely borrowed and modified from configure_parser_config in conda/cli/conda_argparse.py
    """
    descr = """
    Modify configuration values in conda ops managed .condarc. To see more: `conda ops config --help`. To modify other config settings, use `conda config` directly.
    """
    p = subparsers.add_parser("config", description=descr, help=descr, parents=parents)
    p.add_argument("create", nargs="?", const=True, default=False, help="Create conda ops managed .condarc file.")
    _config_subcommands = p.add_argument_group("Config Subcommands")
    config_subcommands = _config_subcommands.add_mutually_exclusive_group()
    config_subcommands.add_argument("--show", nargs="*", default=None, help="Display configuration values in the condaops .condarc file. ")
    config_subcommands.add_argument(
        "--show-sources",
        action="store_true",
        help="Display all identified configuration sources.",
    )
    config_subcommands.add_argument(
        "--validate",
        action="store_true",
        help="Validate all configuration sources. Iterates over all .condarc files " "and checks for parsing errors.",
    )
    config_subcommands.add_argument(
        "--describe",
        nargs="*",
        default=None,
        help="Describe given configuration parameters. If no arguments given, show " "information for all condaops managed configuration parameters.",
    )
    _config_modifiers = p.add_argument_group("Config Modifiers")
    config_modifiers = _config_modifiers.add_mutually_exclusive_group()
    config_modifiers.add_argument(
        "--get",
        nargs="*",
        action="store",
        help="Get a configuration value.",
        default=None,
        metavar="KEY",
    )
    config_modifiers.add_argument(
        "--append",
        nargs=2,
        action="append",
        help="""Add one configuration value to the end of a list key.""",
        default=[],
        metavar=("KEY", "VALUE"),
    )
    config_modifiers.add_argument(
        "--prepend",
        "--add",
        nargs=2,
        action="append",
        help="""Add one configuration value to the beginning of a list key.""",
        default=[],
        metavar=("KEY", "VALUE"),
    )
    config_modifiers.add_argument(
        "--set",
        nargs=2,
        action="append",
        help="""Set a boolean or string key.""",
        default=[],
        metavar=("KEY", "VALUE"),
    )
    config_modifiers.add_argument(
        "--remove",
        nargs=2,
        action="append",
        help="""Remove a configuration value from a list key.
                This removes all instances of the value.""",
        default=[],
        metavar=("KEY", "VALUE"),
    )
    return p


@conda.plugins.hookimpl
def conda_subcommands():
    yield conda.plugins.CondaSubcommand(
        name="ops",
        summary="A conda subcommand that manages your conda environment ops",
        action=conda_ops,
    )
