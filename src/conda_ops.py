import argparse
import conda.plugins

from .commands import consistency_check, lockfile_generate
from .commands_proj import proj_load, proj_create, proj_check
from .commands_reqs import reqs_create, reqs_add, reqs_check, reqs_remove
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
    pip_step_env_lock,
)
from .utils import logger

def conda_ops(argv: list):
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", help="Set the log level")

    parser = argparse.ArgumentParser("conda ops")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="DEBUG", help="Set the log level")
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    # add additional parsers for hidden commands
    proj = subparsers.add_parser("proj", help="Accepts create, check and load", parents=[parent_parser])
    proj.add_argument("kind", type=str)
    env = subparsers.add_parser("env", help="Accepts create, sync, clean, delete, dump, activate, deactivate, check, lockfile-check, regenerate", parents=[parent_parser])
    env.add_argument("kind", type=str)

    reqs = subparsers.add_parser("reqs", help="Accepts create, add, remove, check", parents=[parent_parser])
    reqs_subparser = reqs.add_subparsers(dest="reqs_command", metavar="reqs_command")
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

    lockfile = subparsers.add_parser("lockfile", help="Accepts generate, update, check, reqs-check", parents=[parent_parser])
    lockfile.add_argument("kind", type=str)

    subparsers.add_parser("test")

    args = parser.parse_args(argv)

    logger.setLevel(args.log_level)

    if args.command not in ["init", "proj"]:
        config = proj_load(die_on_error=True)

    if args.command in ["status", None]:
        consistency_check(config=config)
    elif args.command == "proj":
        if args.kind == "create":
            proj_create()
        elif args.kind == "check":
            proj_check()
        elif args.kind == "load":
            proj_load()
    elif args.command == "lockfile":
        if args.kind == "generate":
            lockfile_generate(config, regenerate=True)
        elif args.kind == "update":
            if env_lockfile_check(config, die_on_error=False):
                lockfile_generate(config, regenerate=False)
            else:
                logger.error("Cannot update as environment and lockfile are not in sync.")
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
        elif args.kind == "clean":
            print("call env_clean")
        elif args.kind == "delete":
            env_delete(config)
            logger.info("Conda ops environment deleted.")
        elif args.kind == "lock":
            env_lock(config)
        elif args.kind == "activate":
            env_activate(config=config)
        elif args.kind == "deactivate":
            env_deactivate(config)
        elif args.kind == "check":
            env_check(config)
        elif args.kind == "lockfile-check":
            env_lockfile_check(config)
    elif args.command == "test":
        pip_step_env_lock(config)
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
    else:
        logger.error(f"Unhandled conda ops subcommand: '{args.command}'")


# #############################################################################################
#
# sub-parsers
#
# #############################################################################################


@conda.plugins.hookimpl
def conda_subcommands():
    yield conda.plugins.CondaSubcommand(
        name="ops",
        summary="A conda subcommand that manages your conda environment ops",
        action=conda_ops,
    )
