"""
This module provides functions for managing requirements at the project level.

The functions in this module allow adding, removing, and checking packages in the requirements file.
It also includes helper functions for handling the requirements file and checking consistency of the requirements.

The main functions provided by this module are as follows.

- Requirements Level Functions:
  - reqs_add(packages, channel=None, config=None): Add packages to the requirements file into a given channel section.
  - reqs_remove(packages, config=None): Remove packages from the requirements file.
  - reqs_create(config): Create the requirements file if it doesn't already exist.
  - reqs_check(config, die_on_error=True): Check for the existence and consistency of the requirements file.

- Helper Functions:
  - check_package_in_list(package, package_list, channel=None): Given a package, return the packages in the package_list that match the name of that requirement.
  - clean_package_args(package_args, channel=None): Clean and validate a list of package arguments.
  - pop_pip_section(dependencies): Given the dependencies section of the YAML requirements file, pop the pip section from the dependencies.
  - check_for_duplicates(package_list): Check for duplicate packages in a package list.

Please note that this module relies on other modules and packages within the project, such as .utils.
"""

from pathlib import Path
import os
import subprocess
import sys

from conda.models.match_spec import MatchSpec
from packaging.requirements import Requirement

from .utils import yaml, logger

##################################################################
#
# Requirements Level Functions
#
##################################################################


def reqs_add(packages, channel=None, config=None):
    """
    Add packages to the requirements file from a given channel. By default add the channel to the
    end of the channel order. Treat pip as a special channel.

    TODO: Handle version strings properly
    """
    requirements_file = config["paths"]["requirements"]
    package_str = " ".join(packages)
    if channel:
        logger.info(f"Adding packages {package_str} from channel {channel} to the requirements file {requirements_file}")
    else:
        logger.info(f"Adding packages {package_str} from the conda defaults channel to the requirements file {requirements_file}")

    packages = clean_package_args(packages)

    with open(requirements_file, "r", encoding="utf-8") as yamlfile:
        reqs = yaml.load(yamlfile)

    # pull off the pip section to treat it specially
    reqs["dependencies"], pip_dict = pop_pip_section(reqs["dependencies"])

    for package in packages:
        # check for existing packages and remove them if they have a name match
        conflicts = check_package_in_list(package, reqs["dependencies"])

        if pip_dict is not None:
            pip_conflicts = check_package_in_list(package, pip_dict["pip"])
        else:
            pip_conflicts = []
        if len(conflicts) > 0 or len(pip_conflicts) > 0:
            logger.warning(
                f"Package {package} is in the existing requirements as \
                {' '.join(conflicts)} {' pip::'.join(pip_conflicts)}"
            )
            logger.warning(f"The existing requirements will be replaced withe {package} from channel {channel}")
            for conflict in conflicts:
                reqs["dependencies"].remove(conflict)
            for conflict in pip_conflicts:
                pip_dict["pip"].remove(conflict)
        # add package
        if channel is None:
            if reqs["dependencies"] is None:
                reqs["dependencies"] = [package]
            else:
                reqs["dependencies"] = sorted(reqs["dependencies"] + [package])
        elif channel == "pip":
            if pip_dict is None:
                pip_dict = {"pip": [package]}
            else:
                if len(pip_dict["pip"]) == 0:
                    pip_dict["pip"] = [package]
                else:
                    pip_dict["pip"] = sorted(pip_dict["pip"] + [package])
        else:  # interpret channel as a conda channel
            if reqs["dependencies"] is None:
                reqs["dependencies"] = [f"{channel}::{package}"]
            else:
                reqs["dependencies"] = sorted(reqs["dependencies"] + [f"{channel}::{package}"])
            if channel not in reqs["channel-order"]:
                reqs["channel-order"].append(channel)

    # add back the pip section
    if pip_dict is not None:
        reqs["dependencies"] = [pip_dict] + reqs["dependencies"]

    with open(requirements_file, "w", encoding="utf-8") as yamlfile:
        yaml.dump(reqs, yamlfile)

    print(f"Added packages {package_str} to requirements file.")


def reqs_remove(packages, config=None):
    """
    Remove packages from the requirements file. Treat pip as a special channel.

    TODO: Handle version strings properly
    """
    requirements_file = config["paths"]["requirements"]

    package_str = " ".join(packages)
    logger.info(f"Removing packages {package_str} from the requirements file {requirements_file}")

    packages = clean_package_args(packages)

    with open(requirements_file, "r", encoding="utf-8") as yamlfile:
        reqs = yaml.load(yamlfile)

    # pull off the pip section ot keep it at the beginning of the reqs file
    reqs["dependencies"], pip_dict = pop_pip_section(reqs["dependencies"])

    # first remove non-pip dependencies

    deps = list(set(reqs["dependencies"]))
    for package in packages:
        for dep in deps:
            if "::" in dep:
                dep_check = dep.split("::")[-1].strip()
            else:
                dep_check = dep.strip()
            if dep_check.startswith(package):  # probably need a regex match to get this right
                if dep_check != package:
                    logger.warning(f"Removing {dep} from requirements")
                deps.remove(dep)
    reqs["dependencies"] = sorted(deps)

    # remove any channels that aren't needed anymore
    channel_in_use = []
    for dep in deps:
        if "::" in dep:
            channel, _ = dep.split("::")
            channel_in_use.append(channel)
    new_channel_order = []
    for channel in reqs["channel-order"]:
        if channel == "defaults":
            new_channel_order.append(channel)
        if channel in channel_in_use:
            new_channel_order.append(channel)
    reqs["channel-order"] = new_channel_order

    # now remove pip dependencies if the section exists
    if pip_dict is not None:
        pip_dict["pip"] = list(set(pip_dict["pip"] + packages))
        deps = list(set(pip_dict["pip"]))
        for package in packages:
            for dep in deps:
                if dep.startswith(package):
                    if dep_check != package:  # probably need a proper reges match to get this right
                        logger.warning(f"Removing {dep} from requirements")
                    deps.remove(dep)
        pip_dict["pip"] = sorted(deps)

    # add back the pip section
    if pip_dict is not None:
        if len(pip_dict["pip"]) > 0:
            reqs["dependencies"] = [pip_dict] + reqs["dependencies"]

    with open(requirements_file, "w", encoding="utf-8") as yamlfile:
        yaml.dump(reqs, yamlfile)

    print(f"Removed packages {package_str} to requirements file.")


def reqs_create(config):
    """
    Create the requirements file if it doesn't already exist
    """
    requirements_file = config["paths"]["requirements"]
    env_name = config["settings"]["env_name"]

    if not requirements_file.exists():
        requirements_dict = {
            "name": env_name,
            "channels": ["defaults"],
            "channel-order": ["defaults"],
            "dependencies": sorted(["pip", "python"]),
        }
        logger.info("writing")
        with open(requirements_file, "w", encoding="utf-8") as yamlfile:
            yaml.dump(requirements_dict, yamlfile)
    else:
        logger.info(f"Requirements file {requirements_file} already exists")


def reqs_check(config, die_on_error=True):
    """
    Check for the existence and consistency of the requirements file.

    Return True if the requirements pass all checks and False otherwise
    """
    requirements_file = config["paths"]["requirements"]
    env_name = config["settings"]["env_name"]

    check = True
    if requirements_file.exists():
        logger.debug("Requirements file present")

        with open(requirements_file, "r", encoding="utf-8") as yamlfile:
            requirements = yaml.load(yamlfile)
        if not requirements["name"] == env_name:
            logger.error(
                f"The name in the requirements file {requirements['name']} does not match \
                the name of the managed conda environment {env_name}"
            )
            if input("Would you like to update the environment name in your requirements file (y/n) ").lower() == "y":
                requirements["name"] = env_name
                with open(requirements_file, "w", encoding="utf-8") as yamlfile:
                    yaml.dump(requirements, yamlfile)
            else:
                logger.warning(f"Please check the consistency of your requirements file {requirements_file} manually.")
                check = False
        deps = requirements.get("dependencies", None)
        if deps is None:
            logger.warning("No dependencies found in the requirements file.")
            logger.error("Unimplemented: what to do in this case.")
            check = False
        conda_deps, pip_dict = pop_pip_section(deps)

        # check that the package specifications are valid
        # make the specifications cannonical (warn when changing them)
        valid_specs = []
        invalid_specs = []
        package_name_list = []
        update = False
        for package in conda_deps:
            try:
                req = MatchSpec(package)
                if str(req) != package:
                    update = True
                    logger.warning(f"Requirement {package} will be updated to the cannonical format {str(req)}")
                valid_specs.append(str(req))
                package_name_list.append(req.name)
            except Exception as exception:
                check = False
                print(exception)
                invalid_specs.append(package)
        valid_pip_specs = []
        if pip_dict is not None:
            pip_deps = pip_dict.get("pip", None)
            for package in pip_deps:
                try:
                    req = Requirement(package)
                    if str(req) != package:
                        update = True
                        logger.warning(f"Requirement {package} will be updated to the cannonical format {str(req)}")
                    valid_pip_specs.append(str(req))
                    package_name_list.append(req.name)
                except Exception as exception:
                    check = False
                    print(exception)
                    invalid_specs.append(package)
        if len(invalid_specs) > 0:
            check = False
            logger.error(f"The following specs are of an invalid format: {invalid_specs}.")
            logger.info("Please update them accordingly.")

        # check for duplicate packages
        duplicates = check_for_duplicates(package_name_list)

        if len(duplicates) > 0:
            check = False
            logger.error(f"The packages {list(duplicates.keys())} have been specified more than once.")
            logger.info(f"Please update the requirements file {requirements_file} accordingly.")

        if check and update:
            # only update the file if the specs are all valid
            logger.warning("Updating the requirements file")
            if len(valid_pip_specs) > 0:
                requirements["dependencies"] = [{"pip": valid_pip_specs}] + valid_specs
            else:
                requirements["dependencies"] = valid_specs
            with open(requirements_file, "r") as yamlfile:
                yaml.dump(requirements, yamlfile)
    else:
        check = False
        logger.warning("No requirements file present")
        logger.info("To add a default requirements file to the environment:")
        logger.info(">>> conda ops reqs create")
    if die_on_error and not check:
        sys.exit(1)
    return check


def reqs_list(config):
    """
    Display the contents of the requirements file.
    """
    try:
        with open(config["paths"]["requirements"], "r", encoding="utf-8") as yamlfile:
            reqs = yaml.load(yamlfile)
            print("\n")
            yaml.dump(reqs, sys.stdout)
            print("\n")
    except FileNotFoundError:
        print(f"Requirements file not found.")
        sys.exit(1)


def reqs_edit(config):
    """
    Open the requirements file in the default editor.

    TODO: add the ability to choose a different editor in the configuration.
    """
    filename = config["paths"]["requirements"]
    open_file_in_editor(filename)


############################################
#
# Helper Functions
#
############################################


def check_package_in_list(package, package_list, channel=None):
    """
    Given a package, return the packages in the package_list that match that requirement.
    """
    matching_list = []
    if channel == "pip":
        requirement = Requirement(package)
    else:
        requirement = MatchSpec(package)
    for comp_package in package_list:
        if channel == "pip":
            req_p = Requirement(comp_package)
        else:
            req_p = MatchSpec(comp_package)
        if requirement.name == req_p.name:
            matching_list.append(comp_package)
    return matching_list


def clean_package_args(package_args, channel=None):
    """
    Given a list of packages from the argparser, check that it is in a valid format as per PEP 508.

       - Change package=version to package==version.
       - Split combined strings "python numpy" to "python", "numpy"

    Returns: Cleaned package list or exits.
    """
    # first split packages
    split_packages = []
    for package in package_args:
        if " " in package:
            split_packages.extend(package.split())
        else:
            split_packages.append(package)

    # validate pacakages and modify if it can be done
    invalid_packages = []
    cleaned_packages = []
    for package in split_packages:
        print(package)
        if "=" in package and "==" not in package:
            # Change = to ==
            clean_package = package.replace("=", "==").strip()
        else:
            clean_package = package.strip()
        if channel == "pip":
            # Check PEP 508 compliance

            try:
                req = Requirement(clean_package)
                cleaned_packages.append(req)
            except Exception as exception:
                print(exception)
                invalid_packages.append(package)
        else:
            # Check conda requirement format compliance
            try:
                req = MatchSpec(clean_package)
                cleaned_packages.append(req)
            except Exception as exception:
                print(exception)
                invalid_packages.append(package)

    if len(invalid_packages) > 0:
        logger.error(f"Invalid package format: {' '.join(invalid_packages)}")
        if channel == "pip":
            logger.info("Please fix the entries to be PEP 508 compliant and surrounded by quotes if any version specifications are present")
        else:
            logger.info("Please make sure that these entries are formatted as valid conda specifications.")
        sys.exit(1)

    # check for duplicate packages
    str_packages = [x.name for x in cleaned_packages]
    duplicates = check_for_duplicates(str_packages)
    if len(duplicates) > 0:
        logger.error(f"The packages {duplicates.keys()} have been specified more than once.")
        sys.exit(1)

    return sorted([str(x) for x in cleaned_packages])


def pop_pip_section(dependencies):
    """
    Given the dependencies section of the yaml of the requirements file (in conda environment.yml form),
    pop the pip section from the dependencies.

    Returns:
        (dependencies, pip_section): where the dependencies have the pip_section removed
    """
    # pull off the pip section ot keep it at the beginning of the reqs file
    pip_dict = None
    for k, dep in enumerate(dependencies):
        if isinstance(dep, dict):  # nested yaml
            if dep.get("pip", None):
                pip_dict = dependencies.pop(k)
                break
    return dependencies, pip_dict


def check_for_duplicates(package_list):
    """
    Given a list of packages, look for duplicates and return the indices of the packages.
    """
    # check for duplicate packages
    item_indices = {}
    for i, item in enumerate(package_list):
        if item in item_indices:
            item_indices[item].append(i)
        else:
            item_indices[item] = [i]
    duplicates = {item: indices for item, indices in item_indices.items() if len(indices) > 1}
    return duplicates


def open_file_in_editor(filename, editor=None):
    """
    Open a file in the default text editor based on the platform.

    Arguments:
    - filename (str): The name of the file to open in the editor.
    - editor (str): The name of an editor to open. If set, this takes precedence over any environment variables.

    Raises:
    - subprocess.CalledProcessError: If opening the file in the editor fails.

    Notes:
    - On macOS and Linux, the function uses the 'VISUAL' environment variable to determine the default text editor.
      If 'VISUAL is not set, it falls back to 'EDITOR' and then 'vi'.
    - On Windows, the function uses the 'EDITOR' environment variable if set. If 'EDITOR' is not set, it falls back
      to 'notepad.exe' as the default text editor.
    - For unsupported platforms, the function displays a message indicating that opening the file in the editor is not supported.
    """
    path = Path(filename).resolve()

    if editor is None:
        if sys.platform.startswith("darwin") or sys.platform.startswith("linux"):
            editor = os.environ.get("VISUAL", None)
            if editor is None:
                if sys.platform.startswith("darwin"):
                    # Use 'vim' instead of 'vi' for proper exit codes if no changes are made
                    editor = os.environ.get("EDITOR", "vim")
                else:
                    editor = os.environ.get("EDITOR", "vi")  # Use 'vi' if EDITOR is not set
        elif sys.platform.startswith("win"):
            editor = os.environ.get("EDITOR", "notepad.exe")  # Use 'notepad.exe' if EDITOR is not set
        else:
            print("Unsupported platform: Cannot open file in editor.")
    try:
        subprocess.run([editor, path], check=True)
    except subprocess.CalledProcessError as exception:
        logger.error(f"Failed to open the file in the editor {editor}: {exception}")
