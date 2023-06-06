import argparse

import conda.plugins

from .commands import (ops_init, ops_create, consistency_check,
                       ops_activate, ops_add, ops_sync, ops_lock, ops_delete)


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


    args = parser.parse_args(argv)

    if args.command == 'clean':
        consistency_check()
        print('Removing environment')
        print('Recreating environment from the lock file')
    elif args.command == 'create':
        ops_create()
    elif args.command == 'delete':
        if input("Are you sure you want to delete your conda environment? (y/n) ").lower() != 'y':
                exit()
        else:
            ops_delete()
    elif args.command == 'init':
        ops_init()
    elif args.command == 'install':
        consistency_check()
        package_str = " ".join(args.packages)
        print(f'adding {package_str} to requirements')
        print('creating new lock file')
        print(f'installing packages {package_str}')
        print('DONE')
    elif args.command in ['status', None]:
        consistency_check()
    elif args.command == 'uninstall':
        consistency_check()
        package_str = " ".join(args.packages)
        print(f'removing {package_str} from requirements')
        print('creating new lock file')
        print(f'uninstalling packages {package_str}')
        print('DONE')
    elif args.command == 'sync':
        consistency_check()
        print('updating lock file from requirements')
        print('updating environment')
        print('DONE')
    elif args.command == 'update':
        package_str = " ".join(args.packages)
        print(f'checking {package_str} are in requirements')
        consistency_check()
        print('creating new lock file')
        print(f'updating packages {package_str}')
        print('DONE')
    elif args.command == 'add':
        ops_add(args.packages, channel=args.channel)
    elif args.command == 'lock':
        ops_lock()


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
