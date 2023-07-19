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

from conda.models.match_spec import MatchSpec
from conda.models.version import ver_eval
from packaging.requirements import Requirement
from packaging.version import parse

from .commands_reqs import reqs_check
from .split_requirements import env_split, get_channel_order
from .utils import yaml, logger


##################################################################
#
# Lockfile Level Functions
#
##################################################################


def lockfile_check(config, die_on_error=True):
    """
    Check for the consistency of the lockfile.
    """
    lock_file = config["paths"]["lockfile"]

    check = True
    if lock_file.exists():
        with open(lock_file, "r", encoding="utf-8") as lockfile:
            try:
                json_reqs = json.load(lockfile)
            except Exception as exception:
                check = False
                logger.error(f"Unable to load lockfile {lock_file}")
                logger.debug(exception)
                logger.info("To regenerate the lock file:")
                logger.info(">>> conda ops lockfile regenerate")
                # logger.info(">>> conda ops lock")
            no_url = []
            if json_reqs:
                for package in json_reqs:
                    if package.get("url", None) is None:
                        no_url.append(package["name"])
                        check = False
                    elif package["manager"] == "conda":
                        package_url = (
                            "/".join(
                                [
                                    package["base_url"],
                                    package["platform"],
                                    (package["dist_name"] + package["extension"]),
                                ]
                            ).strip()
                            + f"#{package['md5']}"
                        )
                        if package["url"].strip() != package_url.strip():
                            check = False
                            logger.warning(f"package information for {package['name']} is inconsistent")
                            logger.debug(f"{package_url}, \n{package['url']}")
                            logger.info("To regenerate the lock file:")
                            logger.info(">>> conda ops lockfile regenerate")
                            # logger.info(">>> conda ops lock")
                if len(no_url) > 0:
                    logger.error(f"url(s) for {len(no_url)} packages(s) are missing from the lockfile.")
                    logger.warning(f"The packages {' '.join(no_url)} may not have been added correctly.")
                    logger.warning("Please add any missing packages to the requirements and regenerate the lock file.")
                    logger.info("To regenerate the lock file:")
                    logger.info(">>> conda ops lockfile regenerate")

    else:
        check = False
        logger.error("There is no lock file.")
        logger.info("To create the lock file:")
        logger.info(">>> conda ops lockfile generate")
        # logger.info(">>> conda ops lock")

    if die_on_error and not check:
        sys.exit(1)
    return check


def lockfile_reqs_check(config, reqs_consistent=None, lockfile_consistent=None, die_on_error=True):
    """
    Check the consistency of the lockfile against the requirements file.
    """
    requirements_file = config["paths"]["requirements"]
    lock_file = config["paths"]["lockfile"]

    check = True
    if reqs_consistent is None:
        reqs_consistent = reqs_check(config, die_on_error=die_on_error)

    if lockfile_consistent is None:
        lockfile_consistent = lockfile_check(config, die_on_error=die_on_error)

    if lockfile_consistent and reqs_consistent:
        if requirements_file.stat().st_mtime <= lock_file.stat().st_mtime:
            logger.debug("Lock file is newer than the requirements file")
        else:
            check = False
            logger.warning("The requirements file is newer than the lock file.")
            logger.info("To update the lock file:")
            logger.info(">>> conda ops lockfile regenerate")
            # logger.info(">>> conda ops lock")
        with open(requirements_file, "r", encoding="utf-8") as yamlfile:
            reqs_env = yaml.load(yamlfile)
        channel_order = get_channel_order(reqs_env)
        _, channel_dict = env_split(reqs_env, channel_order)
        with open(lock_file, "r", encoding="utf-8") as jsonfile:
            lock_dict = json.load(jsonfile)
        lock_names = [package["name"] for package in lock_dict]

        # so far we don't check that the channel info is correct, just that the package is there
        missing_packages = []

        for channel in channel_order:
            if channel == "pip":
                pip_cd = channel_dict.get(channel, None)
                if pip_cd:
                    channel_list = [Requirement(x) for x in channel_dict[channel][channel]]
                else:
                    channel_list = []
            else:
                channel_list = [MatchSpec(x) for x in channel_dict[channel]]

            for package in channel_list:
                missing = True
                for lock_package in lock_dict:
                    if package.name == lock_package["name"]:
                        missing = False
                        break
                if missing:
                    missing_packages.append(str(package))
                else:
                    if channel == "pip":
                        if not parse(lock_package["version"]) in package.specifier:
                            missing_packages.append(str(package))
                    else:
                        if package.version and not ver_eval(lock_package["version"], str(package.version)):
                            missing_packages.append(str(package))

        if len(missing_packages) > 0:
            check = False
            logger.error("The following requirements are not in the lockfile:")
            logger.error(f"{' '. join(missing_packages)}")
            logger.info("To update the lock file:")
            logger.info(">>> conda ops lockfile generate")
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
