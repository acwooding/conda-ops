def conda_ops_later(argv: list):
    parser = argparse.ArgumentParser("conda ops")
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    # add subparsers

    add = configure_parser_add(subparsers)
    clean = configure_parser_clean(subparsers)
    create = configure_parser_create(subparsers)
    delete = configure_parser_delete(subparsers)
    init = configure_parser_init(subparsers)
    install = configure_parser_install(subparsers)
    lock = configure_parser_lock(subparsers)
    status = configure_parser_status(subparsers)
    sync = configure_parser_sync(subparsers)
    uninstall = configure_parser_uninstall(subparsers)
    update = configure_parser_update(subparsers)
    activate = configure_parser_activate(subparsers)
    deactivate = configure_parser_deactivate(subparsers)

    if args.command == "activate":
        env_activate(config=config, name=args.name)
    elif args.command == "clean":
        cmd_clean(config)
    elif args.command == "create":
        cmd_create(config=config)
    elif args.command == "deactivate":
        env_deactivate(config)
    elif args.command == "delete":
        if input("Are you sure you want to delete your conda environment? (y/n) ").lower() != "y":
            exit()
        else:
            env_delete(config=config)
            print("To create the environment again:")
            print(">>> conda ops create")

    elif args.command == "init":
        cmd_init()
    elif args.command == "install":
        logger.error("Unimplemented")
        print("DONE")
    elif args.command in ["status", None]:
        consistency_check(config=config)
    elif args.command == "uninstall":
        consistency_check(config=config)
        package_str = " ".join(args.packages)
        print(f"removing {package_str} from requirements")
        print("creating new lock file")
        print(f"uninstalling packages {package_str}")
        print("DONE")
    elif args.command == "sync":
        cmd_sync(config)
        print("DONE")
    elif args.command == "update":
        package_str = " ".join(args.packages)
        print(f"checking {package_str} are in requirements")
        consistency_check(config=config)
        print("creating new lock file")
        print(f"updating packages {package_str}")
        print("DONE")
    elif args.command == "add":
        reqs_add(args.packages, channel=args.channel, config=config)
        print("To update the lockfile accordingly:")
        print(">>> conda ops lock")
    elif args.command == "lock":
        lockfile_regenerate(config)
        logger.info("Lock file genereated")
    elif args.command == "activate":
        cmd_activate()


# #############################################################################################
#
# sub-parsers
#
# #############################################################################################


def configure_parser_activate(subparsers):
    descr = "Activate the managed conda environment"
    p = subparsers.add_parser("activate", description=descr, help=descr)
    p.add_argument(
        "-n",
        "--name",
        help="Name of environment to activate. Default is the environment name in config.ini.",
        action="store",
    )
    return p


def configure_parser_add(subparsers):
    descr = "Add listed packages to the requirements file"
    p = subparsers.add_parser("add", description=descr, help=descr)
    p.add_argument("packages", type=str, nargs="+")
    p.add_argument(
        "-c",
        "--channel",
        help="indicate the channel that the packages are coming from, set this to 'pip' if the packages you are adding are to be installed via pip",
    )


def configure_parser_clean(subparsers):
    descr = "Recreate the environment from the lock file"
    p = subparsers.add_parser("clean", description=descr, help=descr)
    return p


def configure_parser_create(subparsers):
    descr = "Create the conda environment"
    p = subparsers.add_parser("create", description=descr, help=descr)
    return p


def configure_parser_deactivate(subparsers):
    descr = "Deactivate the managed conda environment"
    p = subparsers.add_parser("deactivate", description=descr, help=descr)
    return p


def configure_parser_delete(subparsers):
    descr = "Delete the conda environment"
    p = subparsers.add_parser("delete", description=descr, help=descr)
    return p


def configure_parser_init(subparsers):
    descr = "Initialize conda ops"
    p = subparsers.add_parser("init", description=descr, help=descr)
    return p


def configure_parser_install(subparsers):
    descr = "install the desired packages into the environment"
    p = subparsers.add_parser("install", description=descr, help=descr)

    p.add_argument("packages", type=str, nargs="+")
    p.add_argument(
        "-c",
        "--channel",
        help="indicate the channel that the packages are coming from, set this to 'pip' if the packages you are adding are to be installed via pip",
    )
    return p


def configure_parser_lock(subparsers):
    descr = "Update the lock file based on the requirements file"
    p = subparsers.add_parser("lock", description=descr, help=descr)
    return p


def configure_parser_status(subparsers):
    descr = "Check consistency of requirements, lock file and the environment"
    p = subparsers.add_parser("status", description=descr, help=descr)
    return p


def configure_parser_sync(subparsers):
    descr = "Update the lock file and environment using the requirements file"
    p = subparsers.add_parser("sync", description=descr, help=descr)
    return p


def configure_parser_uninstall(subparsers):
    descr = "Uninstall the listed packages into the environment"
    p = subparsers.add_parser("uninstall", description=descr, help=descr)

    p.add_argument("packages", type=str, nargs="+")
    return p


def configure_parser_update(subparsers):
    descr = "Update listed packages to the latest consistent version"
    p = subparsers.add_parser("update", description=descr, help=descr)
    p.add_argument("packages", type=str, nargs="+")
    return p


############################################
#
# Compound Functions
#
############################################


def cmd_create(config=None):
    """
    Create the first lockfile and environment.

    XXX Possibily init if that hasn't been done yet
    """
    env_name = config["settings"]["env_name"]
    if check_env_exists(env_name):
        logger.error(f"Environment {env_name} exists.")
        logger.info("To activate it:")
        logger.info(f">>> conda activate {env_name}")
        sys.exit(1)

    if not lockfile_reqs_check(config, die_on_error=False):
        lockfile_generate(config)

    env_create(config)


def cmd_sync(config):
    """Generate a lockfile from a requirements file, then update the environment from it."""
    lockfile_generate(config)
    env_sync(config)


def cmd_clean(config):
    """
    Deleted and regenerate the environment from the requirements file. This is the only way to ensure that
    all dependencies of removed requirments are gone.
    """
    env_delete(config)
    lockfile_generate(config)
    env_sync(config)


def cmd_init():
    """
    Initialize the conda ops project by creating a .conda-ops directory including the conda-ops project structure
    """

    config = proj_create()
    reqs_create(config)

    ops_dir = config["paths"]["ops_dir"]
    logger.info(f"Initialized conda-ops project in {ops_dir}")
    print("To create the conda ops environment:")
    print(">>> conda ops create")
