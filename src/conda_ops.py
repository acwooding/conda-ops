import argparse
import logging

import conda.plugins

from .commands import (consistency_check,
                       env_activate, proj_load, env_deactivate, env_regenerate,
                       env_create, env_delete, env_check, env_lockfile_check,
                       env_install, env_lock, lockfile_generate, lockfile_regenerate, proj_create, proj_check,
                       reqs_create, reqs_add, reqs_check, reqs_remove,
                       lockfile_check, lockfile_reqs_check)

logger = logging.getLogger()

def conda_ops(argv: list):
    parser = argparse.ArgumentParser("conda ops")
    subparsers = parser.add_subparsers(dest="command", metavar="command")

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

    if args.command in ['status', None]:
        consistency_check(config=config)
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
        elif args.kind == 'install':
            env_install(config)
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
        logger.info("To update the lock file:")
        logger.info(">>> conda ops lockfile generate")
    elif args.reqs_command == 'remove':
        reqs_remove(args.packages, config=config)
        logger.info("To update the lock file:")
        logger.info(">>> conda ops lockfile regenerate")
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




@conda.plugins.hookimpl
def conda_subcommands():
    yield conda.plugins.CondaSubcommand(
        name="ops",

        summary="A conda subcommand that manages your conda environment ops",
        action=conda_ops,
    )



############################################
#
# Compound Functions
#
############################################



def cmd_create(config=None):
    '''
    Create the first lockfile and environment.

    XXX Possibily init if that hasn't been done yet
    '''
    env_name = config['settings']['env_name']
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
    '''
    Initialize the conda ops project by creating a .conda-ops directory including the conda-ops project structure
    '''

    config = proj_create()
    reqs_create(config)

    ops_dir = config['paths']['ops_dir']
    logger.info(f'Initialized conda-ops project in {ops_dir}')
    print('To create the conda ops environment:')
    print('>>> conda ops create')
