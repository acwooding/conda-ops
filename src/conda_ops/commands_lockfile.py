"""
This module provides functionality for verifying lock files.

It includes functions for checking the consistency of the lock file, and validating the
lock file against the requirements file.

Note that lockfile_generate can be found in commands.py

The main functions provided by this module are:

- lockfile_check: Check the consistency of the lock file.
- lockfile_reqs_check: Check the consistency of the lock file against the requirements file.

Please note that this module depends on other modules and packages within the project, such as .commands,
.commands_env, .commands_reqs, .split_requirements, and .utils. Make sure to install the necessary dependencies
before using the functions in this module.
"""

import json
import sys

from conda.models.version import ver_eval
from packaging.version import parse

from .commands_reqs import reqs_check
from .env_handler import get_conda_info
from .requirements import PackageSpec, LockSpec
from .split_requirements import env_split, get_conda_channel_order
from .utils import yaml, logger


##################################################################
#
# Lockfile Level Functions
#
##################################################################


def lockfile_check(config, die_on_error=True, output_instructions=True, platform=None):
    """
    Check for the consistency of the lockfile.
    """
    lock_file = config["paths"]["lockfile"]

    if platform is None:
        info_dict = get_conda_info()
        platform = info_dict["platform"]

    check = True
    consistency_dict = {}

    if lock_file.exists():
        with open(lock_file, "r", encoding="utf-8") as lockfile:
            try:
                json_reqs = json.load(lockfile)
            except Exception as exception:
                check = False
                logger.warning(f"Unable to load lockfile {lock_file}")
                logger.debug(exception)
                if output_instructions:
                    logger.info("To regenerate the lock file:")
                    logger.info(">>> conda ops sync")

            if json_reqs:
                consistency_dict = lock_package_consistency_check(json_reqs, config, platform)

                if len(consistency_dict["inconsistent"]) > 0:
                    check = False
                    inconsistent_entries = [x.name for x in consistency_dict["inconsistent"]]
                    logger.warning("The lockfile entries for the following pacakges are inconsistent:")
                    logger.info(f"{' '.join(inconsistent_entries)}")
                    if output_instructions:
                        logger.info("To regenerate the lock file:")
                        logger.info(">>> conda ops sync")
                if len(consistency_dict["no_url"]) > 0:
                    check = False
                    no_url = [x.name for x in consistency_dict["no_url"]]
                    logger.warning(f"url(s) for {len(no_url)} packages(s) are missing from the lockfile.")
                    logger.warning(f"The packages {' '.join(no_url)} may not have been added correctly.")
                    logger.warning("Please add any missing packages to the requirements and regenerate the lock file.")
                    if output_instructions:
                        logger.info("To regenerate the lock file:")
                        logger.info(">>> conda ops sync")
                if len(consistency_dict["no_url_lookup"]) > 0:
                    no_url_lookup = [x.name for x in consistency_dict["no_url_lookup"]]
                    check = False
                    logger.warning(f"url lookup(s) for {len(no_url_lookup)} packages(s) are missing from the local url lookup file.")
                    logger.warning(f"The entries for the package(s) {' '.join(no_url_lookup)} need to be regenerated.")
                    if output_instructions:
                        logger.info("To regenerate the lock file:")
                        logger.info(">>> conda ops sync")
                if not consistency_dict["platform_in_lockfile"]:
                    check = False
                    logger.warning(f"A lock file exists but has no packages for the platform: {platform}")
                    if output_instructions:
                        logger.info("To update the lock file:")
                        logger.info(">>> conda ops sync")
    else:
        check = False
        logger.warning("There is no lock file.")
        if output_instructions:
            logger.info("To create the lock file:")
            logger.info(">>> conda ops sync")

    if die_on_error and not check:
        sys.exit(1)
    return check, consistency_dict


def lock_package_consistency_check(lockfile_json_reqs, config, platform):
    """
    Given a list of lockfile json reqs, check each package for:
    * consistency_check
    * check for a url
    * if it is a local url, check the lookup exists

    Further check that a given platform appears in the lockfile json reqs at least once.

    Return a dict with the lists of requirement entries that that fail the checks, and with an entry to
    specify if the given platform is in the lockfile.
    """
    consistency_dict = {"inconsistent": [], "no_url": [], "no_url_lookup": [], "platform_in_lockfile": False}

    for package in lockfile_json_reqs:
        lock_package = LockSpec.from_lock_entry(package, config=config)
        if lock_package.platform == platform:
            consistency_dict["platform_in_lockfile"] = True
            if not lock_package.check_consistency():
                consistency_dict["inconsistent"].append(lock_package)
            if lock_package.url is None:
                consistency_dict["no_url"].append(lock_package)
            if lock_package.url == "":
                consistency_dict["no_url_lookup"].append(lock_package)

    return consistency_dict


def lockfile_reqs_check(config, reqs_consistent=None, lockfile_consistent=None, die_on_error=True, output_instructions=True):
    """
    Check the consistency of the lockfile against the requirements file.
    """
    requirements_file = config["paths"]["requirements"]
    lock_file = config["paths"]["lockfile"]

    check = True
    if reqs_consistent is None:
        reqs_consistent = reqs_check(config, die_on_error=die_on_error)

    if lockfile_consistent is None:
        lockfile_consistent, _ = lockfile_check(config, die_on_error=die_on_error)

    if lockfile_consistent and reqs_consistent:
        ## TODO: I think this can be removed since we explicitly check if the lockfile
        ## satisfies the requirements
        if requirements_file.stat().st_mtime <= lock_file.stat().st_mtime:
            logger.debug("Lock file is newer than the requirements file")
        else:
            check = False
            logger.debug("The requirements file is newer than the lock file.")
            if output_instructions:
                logger.info("To update the lock file:")
                logger.info(">>> conda ops sync")
        with open(requirements_file, "r", encoding="utf-8") as yamlfile:
            reqs_env = yaml.load(yamlfile)
        channel_order = get_conda_channel_order(reqs_env)
        _, channel_dict = env_split(reqs_env, channel_order)
        with open(lock_file, "r", encoding="utf-8") as jsonfile:
            lock_dict = json.load(jsonfile)

        # so far we don't check that the channel info is correct, just that the package is there
        missing_packages = []
        for channel in channel_order + ["pip"]:
            channel_list = [PackageSpec(req, channel=channel) for req in channel_dict[channel]]
            for package in channel_list:
                missing = True
                check_version = False
                for lock_package in lock_dict:
                    if package.is_pathspec:
                        # this is a url based requirement
                        # look for the spec in the package url
                        if package.requirement.spec in lock_package["url"]:
                            missing = False
                    else:
                        try:
                            package_name = package.name
                        except AttributeError as e:
                            print(e)
                            ## Unimplimented for now
                            package_name = None
                        if package_name == lock_package["name"]:
                            # find the matching package
                            missing = False
                            check_version = True
                            break
                if missing:
                    missing_packages.append(package)
                if check_version:
                    if channel == "pip":
                        if not parse(lock_package["version"]) in package.version:
                            missing_packages.append(package)
                    else:
                        if package.version and not ver_eval(lock_package["version"], str(package.version)):
                            missing_packages.append(package)

        if len(missing_packages) > 0:
            check = False
            logger.info("The following requirements are not in the lockfile:")
            logger.info(f"   {', '. join([x.to_reqs_entry() for x in missing_packages])}")
            if output_instructions:
                logger.info("To update the lock file:")
                logger.info(">>> conda ops sync")
    else:
        if not reqs_consistent:
            logger.error("Cannot check lockfile against requirements as the requirements file is missing or inconsistent.")
            check = False
        elif not lockfile_consistent:
            logger.error("Cannot check lockfile against requirements as the lock file is missing or inconsistent.")
            check = False

    if die_on_error and not check:
        sys.exit(1)
    return check
