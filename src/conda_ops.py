import argparse
import conda.plugins

from .commands import consistency_check, lockfile_generate
from .commands_proj import proj_load, proj_create
from .commands_reqs import reqs_create, reqs_add, reqs_remove, reqs_list, reqs_edit
from .commands_lockfile import lockfile_check, lockfile_reqs_check
from .commands_env import (
    env_activate,
    env_deactivate,
    env_regenerate,
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
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", help="Set the log level")

    parser = argparse.ArgumentParser("conda ops", parents=[parent_parser])
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    init = configure_parser_init(subparsers, parents=[parent_parser])
    config_parser = configure_parser_config(subparsers, parents=[parent_parser])
    reqs = configure_parser_reqs(subparsers, parents=[parent_parser])
    lockfile = subparsers.add_parser("lockfile", help="Operations for managing the lockfile. Accepts generate, check, reqs-check.", parents=[parent_parser])
    lockfile.add_argument("kind", choices=["generate", "check", "reqs-check"])
    env = subparsers.add_parser("env", help="Operations for managing the environment. Accepts create, install, delete, regenerate, check, lockfile-check.", parents=[parent_parser])
    env.add_argument("kind", choices=["create", "delete", "activate", "deactivate", "check", "lockfile-check", "regenerate", "install"])

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
        proj_create()
        config = proj_load()
        condarc_create(config=config)
        if not config["paths"]["requirements"].exists():
            reqs_create(config=config)
        else:
            logger.info("Requirements file already exists")
    elif args.command == "lockfile":
        if args.kind == "generate":
            lockfile_generate(config, regenerate=True)
        elif args.kind == "check":
            check = lockfile_check(config)
            if check:
                logger.info("Lockfile is consistent")
        elif args.kind == "reqs-check":
            check = lockfile_reqs_check(config)
            if check:
                logger.info("Lockfile and requirements are consistent")
    elif args.command == "env":
        if args.kind == "create":
            env_create(config)
        if args.kind == "regenerate":
            env_regenerate(config=config)
        elif args.kind == "install":
            env_install(config)
        elif args.kind == "delete":
            env_delete(config)
            logger.info("Conda ops environment deleted.")
        elif args.kind == "activate":
            env_activate(config=config)
        elif args.kind == "deactivate":
            env_deactivate(config)
        elif args.kind == "check":
            env_check(config)
        elif args.kind == "lockfile-check":
            env_lockfile_check(config)
    elif args.command == "test":
        check_condarc_matches_opinions(config=config)
    elif args.reqs_command == "create":
        reqs_create(config)
    elif args.reqs_command == "add":
        reqs_add(args.packages, channel=args.channel, config=config)
        logger.info("To update the lock file:")
        logger.info(">>> conda ops lockfile generate")
    elif args.reqs_command == "remove":
        reqs_remove(args.packages, config=config)
        logger.info("To update the lock file:")
        logger.info(">>> conda ops lockfile regenerate")
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
# sub-parsers
#
# #############################################################################################


def configure_parser_init(subparsers, parents):
    descr = "Create a conda ops project in the current directory"
    p = subparsers.add_parser("init", description=descr, help=descr, parents=parents)
    return p


def configure_parser_reqs(subparsers, parents):
    descr = "Operations for managing the requirements file. Accepts arguments create, add, remove, check, list, edit."
    p = subparsers.add_parser("reqs", help=descr, parents=parents)
    reqs_subparser = p.add_subparsers(dest="reqs_command", metavar="reqs_command")
    reqs_subparser.add_parser("create")
    r_add = reqs_subparser.add_parser("add")
    r_add.add_argument("packages", type=str, nargs="+")
    r_add.add_argument(
        "-c",
        "--channel",
        help="indicate the channel that the packages are coming from, set this to 'pip' \
        if the packages you are adding are to be installed via pip",
    )
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
    Modify configuration values in conda ops managed .condarc. This will show and modify conda-ops
    managed configuration settings. To modify other config settings, use `conda config` directly.
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
