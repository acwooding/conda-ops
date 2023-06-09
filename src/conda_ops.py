import argparse
import logging

import conda.plugins

from .commands import (cmd_init, cmd_create, consistency_check, cmd_clean,
                       env_activate, cmd_sync, proj_load, env_deactivate, env_regenerate,
                       env_create, env_delete, env_check, env_lockfile_check,
                       env_sync, env_lock, lockfile_generate, lockfile_regenerate, proj_create, proj_check,
                       reqs_create, reqs_add, reqs_check, reqs_remove,
                       lockfile_check, lockfile_reqs_check)

logger = logging.getLogger()

def conda_ops(argv: list):
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

    # add additional parsers for hidden commands
    proj = subparsers.add_parser('proj', help='Accepts create, check and load')
    proj.add_argument('kind', type=str)
    env = subparsers.add_parser('env', help='Accepts create, sync, clean, delete, dump, activate, deactivate, check, lockfile-check, regenerate')
    env.add_argument('kind', type=str)

    reqs = subparsers.add_parser('reqs', help='Accepts create, add, remove, check')
    reqs_subparser = reqs.add_subparsers(dest='reqs_command', metavar='reqs_command')
    reqs_subparser.add_parser('create')
    r_add = reqs_subparser.add_parser('add')
    r_add.add_argument('packages', type=str, nargs='+')
    r_add.add_argument('-c', '--channel', help="indicate the channel that the packages are coming from, set this to 'pip' if the packages you are adding are to be installed via pip")
    r_remove = reqs_subparser.add_parser('remove')
    r_remove.add_argument('packages', type=str, nargs='+')
    reqs_subparser.add_parser('check')

    lockfile = subparsers.add_parser('lockfile', help='Accepts generate, regenerate, update, check, reqs-check')
    lockfile.add_argument('kind', type=str)


    args = parser.parse_args(argv)

    if not args.command in ['init', 'proj']:
        config = proj_load(die_on_error=True)

    if args.command == 'activate':
        env_activate(config=config, name=args.name)
    elif args.command == 'clean':
        cmd_clean(config)
    elif args.command == 'create':
        cmd_create(config=config)
    elif args.command == 'deactivate':
        env_deactivate(config)
    elif args.command == 'delete':
        if input("Are you sure you want to delete your conda environment? (y/n) ").lower() != 'y':
                exit()
        else:
            env_delete(config=config)
            print("To create the environment again:")
            print(">>> conda ops create")

    elif args.command == 'init':
        cmd_init()
    elif args.command == 'install':
        logger.error("Unimplemented")
        print('DONE')
    elif args.command in ['status', None]:
        consistency_check(config=config)
    elif args.command == 'uninstall':
        consistency_check(config=config)
        package_str = " ".join(args.packages)
        print(f'removing {package_str} from requirements')
        print('creating new lock file')
        print(f'uninstalling packages {package_str}')
        print('DONE')
    elif args.command == 'sync':
        cmd_sync(config)
        print('DONE')
    elif args.command == 'update':
        package_str = " ".join(args.packages)
        print(f'checking {package_str} are in requirements')
        consistency_check(config=config)
        print('creating new lock file')
        print(f'updating packages {package_str}')
        print('DONE')
    elif args.command == 'add':
        reqs_add(args.packages, channel=args.channel, config=config)
        print('To update the lockfile accordingly:')
        print('>>> conda ops lock')
    elif args.command == 'lock':
        lockfile_regenerate(config)
        logger.info("Lock file genereated")
    elif args.command == 'activate':
        cmd_activate()
    elif args.command == 'proj':
        if args.kind == 'create':
            proj_create()
        elif args.kind == 'check':
            proj_check()
        elif args.kind == 'load':
            proj_load()
    elif args.command == 'lockfile':
        if args.kind == 'generate':
            lockfile_generate(config)
        elif args.kind == 'regenerate':
            lockfile_regenerate(config)
        elif args.kind == 'check':
            check = lockfile_check(config)
            if check:
                logger.info("Lockfile is consistent")
        elif args.kind == 'update':
            print('call lockfile_update')
        elif args.kind == 'reqs-check':
            check = lockfile_reqs_check(config)
            if check:
                logger.info("Lockfile and requirements are consistent")
    elif args.command == 'env':
        if args.kind == 'create':
            env_create(config)
        if args.kind == 'regenerate':
            env_regenerate(config=config)
        elif args.kind == 'sync':
            env_sync(config)
        elif args.kind == 'clean':
            print('call env_clean')
        elif args.kind == 'delete':
            env_delete(config)
        elif args.kind == 'lock':
            env_lock(config)
        elif args.kind == 'activate':
            env_activate(config=config)
        elif args.kind == 'deactivate':
            env_deactivate(config)
        elif args.kind == 'check':
            env_check(config)
        elif args.kind == 'lockfile-check':
            env_lockfile_check(config)
    elif args.reqs_command == 'create':
        reqs_create(config)
    elif args.reqs_command == 'add':
        reqs_add(args.packages, channel=args.channel, config=config)
    elif args.reqs_command == 'remove':
        reqs_remove(args.packages, config=config)
    elif args.reqs_command == 'check':
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


def configure_parser_activate(subparsers):
    descr = "Activate the managed conda environment"
    p = subparsers.add_parser(
        'activate',
        description=descr,
        help=descr
    )
    p.add_argument("-n", "--name", help="Name of environment to activate. Default is the environment name in config.ini.",
                   action="store")
    return p

def configure_parser_add(subparsers):
    descr = 'Add listed packages to the requirements file'
    p = subparsers.add_parser(
        'add',
        description=descr,
        help=descr
    )
    p.add_argument('packages', type=str, nargs='+')
    p.add_argument('-c', '--channel', help="indicate the channel that the packages are coming from, set this to 'pip' if the packages you are adding are to be installed via pip")

def configure_parser_clean(subparsers):
    descr = 'Recreate the environment from the lock file'
    p = subparsers.add_parser(
        'clean',
        description=descr,
        help=descr
    )
    return p

def configure_parser_create(subparsers):
    descr = 'Create the conda environment'
    p = subparsers.add_parser(
        'create',
        description=descr,
        help=descr
    )
    return p

def configure_parser_deactivate(subparsers):
    descr = "Deactivate the managed conda environment"
    p = subparsers.add_parser(
        'deactivate',
        description=descr,
        help=descr
    )
    return p

def configure_parser_delete(subparsers):
    descr = 'Delete the conda environment'
    p = subparsers.add_parser(
        'delete',
        description=descr,
        help=descr
    )
    return p

def configure_parser_init(subparsers):
    descr = 'Initialize conda ops'
    p = subparsers.add_parser(
        'init',
        description=descr,
        help=descr
    )
    return p

def configure_parser_install(subparsers):
    descr = 'install the desired packages into the environment'
    p = subparsers.add_parser(
        'install',
        description=descr,
        help=descr
    )

    p.add_argument('packages', type=str, nargs='+')
    p.add_argument('-c', '--channel', help="indicate the channel that the packages are coming from, set this to 'pip' if the packages you are adding are to be installed via pip")
    return p

def configure_parser_lock(subparsers):
    descr = 'Update the lock file based on the requirements file'
    p = subparsers.add_parser(
        'lock',
        description=descr,
        help=descr
    )
    return p

def configure_parser_status(subparsers):
    descr = 'Check consistency of requirements, lock file and the environment'
    p = subparsers.add_parser(
        'status',
        description=descr,
        help=descr
    )
    return p

def configure_parser_sync(subparsers):
    descr = 'Update the lock file and environment using the requirements file'
    p = subparsers.add_parser(
        'sync',
        description=descr,
        help=descr
    )
    return p

def configure_parser_uninstall(subparsers):
    descr = 'Uninstall the listed packages into the environment'
    p = subparsers.add_parser(
        'uninstall',
        description=descr,
        help=descr
    )

    p.add_argument('packages', type=str, nargs='+')
    return p

def configure_parser_update(subparsers):
    descr = 'Update listed packages to the latest consistent version'
    p = subparsers.add_parser(
        'update',
        description=descr,
        help=descr
    )
    p.add_argument('packages', type=str, nargs='+')
    return p




@conda.plugins.hookimpl
def conda_subcommands():
    yield conda.plugins.CondaSubcommand(
        name="ops",

        summary="A conda subcommand that manages your conda environment ops",
        action=conda_ops,
    )
