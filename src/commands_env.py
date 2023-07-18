import json
from pathlib import Path
import re
import subprocess
import sys
from io import StringIO
import urllib
from contextlib import redirect_stdout

from packaging.requirements import Requirement

from .python_api import run_command
from .commands_proj import proj_load, get_conda_info, CondaOpsManagedCondarc
from .conda_config import env_pip_interop
from .commands_lockfile import lockfile_check
from .utils import logger

##################################################################
#
# Environment Level Functions
#
##################################################################


def env_activate(*, config=None, name=None):
    """Activate the managed environment"""
    env_name = config["settings"]["env_name"]
    if name is None:
        name = env_name
    if name != env_name:
        logger.warning(f"Requested environment {name} which does not match the conda ops managed environment {env_name}")
    if check_env_active(env_name):
        logger.warning(f"The conda ops environment {env_name} is already active.")
    else:
        logger.info("To activate the conda ops environment:")
        logger.info(f">>> conda activate {env_name}")


def env_deactivate(config):
    """Deactivate managed conda environment"""

    env_name = config["settings"]["env_name"]
    conda_info = get_conda_info()
    active_env = conda_info["active_prefix_name"]

    if active_env != env_name:
        logger.warning("The active environment is {active_env}, not the conda ops managed environment {env_name}")

    logger.info(f"To deactivate the environment {active_env}:")
    logger.info(">>> conda deactivate")


def env_create(config=None, env_name=None, lock_file=None):
    """
    Create the conda ops managed environment from the lock file
    """
    if env_name is None:
        env_name = config["settings"]["env_name"]
    if check_env_exists(env_name):
        logger.error(f"Environment {env_name} exists.")
        logger.info("To activate it:")
        logger.info(f">>> conda activate {env_name}")
        sys.exit(1)

    if lock_file is None:
        lock_file = config["paths"]["lockfile"]

    if not lock_file.exists():
        logger.error(f"The lockfile does not exist: {lock_file}")
        logger.info("To generate a lockfile:")
        logger.info(">>> conda ops lockfile generate")
        sys.exit(1)
    explicit_files = generate_explicit_lock_files(config, lock_file=lock_file)

    explicit_lock_file = config["paths"]["explicit_lockfile"]
    logger.info(f"Creating the environment {env_name}")
    prefix = get_prefix(env_name)
    with CondaOpsManagedCondarc(config["paths"]["condarc"]):
        conda_args = ["--prefix", prefix, "--file", str(explicit_lock_file)]
        stdout, stderr, result_code = run_command("create", conda_args)
        if result_code != 0:
            logger.error(stdout)
            logger.error(stderr)
            sys.exit(result_code)
    logger.info(stdout)

    pip_lock_file = config["paths"]["pip_explicit_lockfile"]
    if pip_lock_file in explicit_files:
        logger.info("Installing pip managed dependencies...")

        # Workaround for the issue in conda version 23.5.0 (and greater?) see issues.
        # We need to capture the pip install output to get the exact filenames of the packages
        with CondaOpsManagedCondarc(config["paths"]["condarc"]):
            stdout_backup = sys.stdout
            sys.stdout = capture_output = StringIO()
            with redirect_stdout(capture_output):
                conda_args = ["--prefix", get_prefix(env_name), "pip", "install", "-r", str(pip_lock_file), "--verbose"]
                stdout, stderr, result_code = run_command("run", conda_args)
                if result_code != 0:
                    logger.error(stdout)
                    logger.error(stderr)
                    sys.exit(result_code)
            sys.stdout = stdout_backup
            stdout_str = capture_output.getvalue()
            logger.info(stdout_str)

    logger.info("Environment created. To activate the environment:")
    logger.info(f">>> conda activate {env_name}")


def env_lock(config, lock_file=None, env_name=None, pip_dict=None):
    """
    Generate a lockfile from the contents of the environment.
    """
    if env_name is None:
        env_name = config["settings"]["env_name"]
    if lock_file is None:
        lock_file = config["paths"]["lockfile"]

    if not check_env_exists(env_name):
        logger.error(f"No environment {env_name} exists")
        sys.exit(1)

    # json requirements
    # need to use a subprocess to get any newly installed python package information
    # that was installed via pip
    with CondaOpsManagedCondarc(config["paths"]["condarc"]):
        conda_args = ["--prefix", get_prefix(env_name), "--json"]
        result = subprocess.run(["conda", "list"] + conda_args, capture_output=True, check=False)
        result_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
        if result_code != 0:
            logger.error(stdout)
            logger.error(stderr)
            sys.exit(result_code)

    json_reqs = json.loads(stdout)

    # explicit requirements to get full urls and md5 of conda packages
    with CondaOpsManagedCondarc(config["paths"]["condarc"]):
        conda_args = ["--prefix", get_prefix(env_name), "--explicit", "--md5"]
        stdout, stderr, result_code = run_command("list", conda_args, use_exception_handler=True)
        if result_code != 0:
            logger.error(stdout)
            logger.error(stderr)
            sys.exit(result_code)
    explicit = [x for x in stdout.split("\n") if "https" in x]

    # add additional information to go into the lock file based on the kind of package
    logger.debug(f"Environment to be locked with {len(json_reqs)} packages")
    for package in json_reqs:
        if package["channel"] == "pypi":
            package["manager"] = "pip"
            if pip_dict is not None:
                pip_dict_entry = pip_dict.get(package["name"], None)
                if pip_dict_entry is not None:
                    if pip_dict_entry["version"] != package["version"]:
                        logger.error(
                            f"The pip extra info entry version {pip_dict_entry['version']} does \
                            not match the conda package version{package['version']}"
                        )
                        sys.exit(1)
                    else:
                        package["url"] = pip_dict_entry["url"]
                        package["sha256"] = pip_dict_entry["sha256"]
                        package["filenmae"] = pip_dict_entry["filename"]
        else:
            starter_str = "/".join([package["base_url"], package["platform"], package["dist_name"]])
            line = None
            for line in explicit:
                if starter_str in line:
                    break
            if line:
                md5_split = line.split("#")
                package["md5"] = md5_split[-1]
                package["extension"] = md5_split[0].split(f"{package['dist_name']}")[-1]
                package["url"] = line
                package["manager"] = "conda"

    blob = json.dumps(json_reqs, indent=2, sort_keys=True)
    with open(lock_file, "w", encoding="utf-8") as jsonfile:
        jsonfile.write(blob)

    return json_reqs


def conda_step_env_lock(channel, config, env_name=None):
    """
    Given a conda channel from the channel order list, update the environment and generate a new lock file.
    """
    if env_name is None:
        env_name = config["settings"]["env_name"]
    ops_dir = config["paths"]["ops_dir"]

    logger.info(f"Generating the intermediate lock file for channel {channel} via environment {env_name}")

    with open(ops_dir / f".ops.{channel}-environment.txt", encoding="utf-8") as reqsfile:
        package_list = reqsfile.read().split()

    if len(package_list) == 0:
        logger.warning("No packages to be installed at this step")
        return {}
    prefix = get_prefix(env_name)
    if check_env_exists(env_name):
        conda_args = ["--prefix", prefix, "-c", channel] + package_list
        with CondaOpsManagedCondarc(config["paths"]["condarc"]):
            stdout, stderr, result_code = run_command("install", conda_args)
            if result_code != 0:
                logger.error(stdout)
                logger.error(stderr)
                return None
            print(stdout)
    else:
        # create the environment directly
        logger.debug(f"Creating environment {env_name} at {prefix} ")
        with CondaOpsManagedCondarc(config["paths"]["condarc"]):
            conda_args = ["--prefix", prefix, "-c", channel] + package_list
            stdout, stderr, result_code = run_command("create", conda_args, use_exception_handler=True)
            if result_code != 0:
                logger.error(stdout)
                logger.error(stderr)
                return None
            print(stdout)

    channel_lockfile = ops_dir / f".ops.lock.{channel}"
    json_reqs = env_lock(config=config, lock_file=channel_lockfile, env_name=env_name)

    return json_reqs


def pip_step_env_lock(config, env_name=None):
    """
    Update the environment with the pip requirements and generate a new lock file.
    """
    # set the pip interop flag to True as soon as pip packages are to be installed so conda remain aware of it
    # possibly set this at the first creation of the environment so it's always True

    if env_name is None:
        env_name = config["settings"]["env_name"]

    env_pip_interop(config=config, flag=True)

    ops_dir = config["paths"]["ops_dir"]
    logger.info(f"Generating the intermediate lock file for pip via environment {env_name}")

    pypi_reqs_file = ops_dir / ".ops.pypi-requirements.txt"

    # Workaround for the issue in cconda version 23.5.0 (and greater?) see issues.
    # We need to capture the pip install output to get the exact filenames of the packages
    with CondaOpsManagedCondarc(config["paths"]["condarc"]):
        stdout_backup = sys.stdout
        sys.stdout = capture_output = StringIO()
        with redirect_stdout(capture_output):
            conda_args = ["--prefix", get_prefix(env_name), "pip", "install", "-r", str(pypi_reqs_file), "--verbose"]
            stdout, stderr, result_code = run_command("run", conda_args, use_exception_handler=True)
            if result_code != 0:
                logger.error(stdout)
                logger.error(stderr)
                return None
        sys.stdout = stdout_backup
        stdout_str = capture_output.getvalue()
        print(stdout_str)

    pip_dict = extract_pip_installed_filenames(stdout_str, config=config)

    channel_lockfile = ops_dir / ".ops.lock.pip"
    json_reqs = env_lock(config, lock_file=channel_lockfile, env_name=env_name, pip_dict=pip_dict)

    with open(ops_dir / ".ops.sdist-requirements.txt", encoding="utf-8") as reqsfile:
        sdist_list = reqsfile.read().split("\n")
    logger.error(f"TODO: Implement the pip step for sdists and editable modules {sdist_list}")

    return json_reqs


def env_check(config=None, die_on_error=True):
    """
    Check that the conda ops environment exists and is active.
    """
    if config is None:
        config = proj_load()

    check = True

    env_name = config["settings"]["env_name"]

    info_dict = get_conda_info()
    active_conda_env = info_dict["active_prefix_name"]
    platform = info_dict["platform"]

    logger.info(f"Active Conda environment: {active_conda_env}")
    logger.info(f"Conda platform: {platform}")
    if check_env_active(env_name):
        pass
    else:
        env_exists = check_env_exists(env_name)
        if env_exists:
            check = False
            logger.warning(f"Managed conda environment ('{env_name}') exists but is not active.")
            logger.info("To activate it:")
            logger.info(f">>> conda activate {env_name}")
        else:
            check = False
            logger.warning(f"Managed conda environment ('{env_name}') does not yet exist.")
            logger.info("To create it:")
            logger.info(">>> conda ops env create")
            # logger.info(">>> conda ops create")
    if die_on_error and not check:
        sys.exit(1)
    return check


def env_lockfile_check(config=None, env_consistent=None, lockfile_consistent=None, die_on_error=True):
    """
    Check that the environment and the lockfile are in sync
    """
    if config is None:
        config = proj_load()

    env_name = config["settings"]["env_name"]

    if lockfile_consistent is None:
        lockfile_consistent = lockfile_check(config, die_on_error=die_on_error)

    if not lockfile_consistent:
        logger.warning("Lock file is missing or inconsistent. Cannot determine the consistency of the lockfile and environment.")
        logger.info("To lock the environment:")
        logger.info(">>> conda ops lockfile generate")
        # logger.info(">>> conda ops lock")
        if die_on_error:
            sys.exit(1)
        else:
            return False

    if env_consistent is None:
        env_consistent = env_check(config, die_on_error=die_on_error)

    if not env_consistent:
        logger.warning(
            "Environment does not exist or is not active. Cannot determine the consistency \
            of the lockfile and environment."
        )
        if die_on_error:
            sys.exit(1)
        else:
            return False

    check = True

    logger.debug(f"Enumerating packages from the conda ops environment {env_name}")

    with CondaOpsManagedCondarc(config["paths"]["condarc"]):
        conda_args = ["--prefix", get_prefix(env_name), "--explicit", "--md5"]
        stdout, stderr, result_code = run_command("list", conda_args, use_exception_handler=True)
        if result_code != 0:
            logger.error("Could not get packages from the environment")
            logger.error(stdout)
            logger.error(stderr)
            if die_on_error:
                sys.exit(result_code)
            else:
                return False

    conda_set = {x for x in stdout.split("\n") if "https" in x}
    logger.debug(f"Found {len(conda_set)} conda package(s) in environment: {env_name}")

    # generate the explicit lock file and load it
    explicit_files = generate_explicit_lock_files(config)
    explicit_lock_file = config["paths"]["explicit_lockfile"]

    with open(explicit_lock_file, "r", encoding="utf-8") as explicitfile:
        lock_contents = explicitfile.read()
    lock_set = {x for x in lock_contents.split("\n") if "https" in x}

    if conda_set == lock_set:
        logger.debug("Conda packages in environment and lock file are in sync.\n")
    else:
        check = False
        logger.warning("The lock file and environment are not in sync")
        in_env = conda_set.difference(lock_set)
        in_lock = lock_set.difference(conda_set)
        if len(in_env) > 0:
            logger.debug("\nThe following packages are in the environment but not in the lock file:\n")
            logger.debug("\n".join(in_env))
            logger.debug("\n")
            logger.info("To restore the environment to the state of the lock file")
            logger.info(">>> conda deactivate")
            logger.info(">>> conda ops env regenerate")
            logger.info(f">>> conda activate {env_name}")
            # logger.info(">>> conda ops sync")
        if len(in_lock) > 0:
            logger.debug("\nThe following packages are in the lock file but not in the environment:\n")
            logger.debug("\n".join(in_lock))
            logger.debug("\n")
            logger.info("To add these packages to the environment:")
            logger.info(">>> conda ops env install")
            # logger.info(">>> conda ops sync")

    # check that the pip contents of the lockfile match the conda environment

    # need to use a subprocess to ensure we get all of the pip package info
    with CondaOpsManagedCondarc(config["paths"]["condarc"]):
        conda_args = ["--prefix", get_prefix(env_name), "--json"]
        result = subprocess.run(["conda", "list"] + conda_args, capture_output=True, check=False)
        result_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
        if result_code != 0:
            logger.error(f"Could not get pip packages from the environment {env_name}")
            logger.info(f"stdout: {stdout}")
            logger.info(f"stderr: {stderr}")
            if die_on_error:
                sys.exit(result_code)
            else:
                return False
    conda_list = json.loads(stdout)

    conda_dict = {}
    for package in conda_list:
        if package["channel"] == "pypi":
            conda_dict[package["name"]] = package["version"]

    logger.debug(f"Found {len(conda_dict)} pip package(s) in environment: {env_name}")

    if len(explicit_files) > 1:
        env_pip_interop(config=config, flag=True)

        logger.info("Checking consistency of pip installed packages...")
        logger.debug("Note that we only compare the package name and version number as this is all conda list gives us")
        lock_dict = {}
        lockfile = config["paths"]["lockfile"]
        with open(lockfile, "r", encoding="utf-8") as jsonfile:
            lock_list = json.load(jsonfile)
        for package in lock_list:
            if package["channel"] == "pypi":
                lock_dict[package["name"]] = package["version"]

        if conda_dict == lock_dict:
            logger.debug("Pip packages in environment and lock file are in sync.\n")
        else:
            check = False
            # Find differing packages
            in_env = set(conda_dict.keys()).difference(lock_dict.keys())
            in_lock = set(lock_dict.keys()).difference(conda_dict.keys())
            if len(in_env) > 0:
                logger.debug("\nThe following packages are in the environment but not in the lock file:\n")
                logger.debug(", ".join(in_env))
                logger.debug("\n")
                logger.info("To restore the environment to the state of the lock file")
                logger.info(">>> conda deactivate")
                logger.info(">>> conda ops env regenerate")
                logger.info(f">>> conda activate {env_name}")
                # logger.info(">>> conda ops sync")
            if len(in_lock) > 0:
                logger.debug("\nThe following packages are in the lock file but not in the environment:\n")
                logger.debug(", ".join(in_lock))
                logger.debug("\n")
                logger.info("To add these packages to the environment:")
                logger.info(">>> conda ops env install")
                # logger.info(">>> conda ops sync")
            # Find differing versions
            differing_versions = {key: (conda_dict[key], lock_dict[key]) for key in conda_dict if key in lock_dict and conda_dict[key] != lock_dict[key]}
            if len(differing_versions) > 0:
                logger.debug("\nThe following package versions don't match:\n")
                logger.debug("\n".join([f"{x}: Lock version {lock_dict[x]}, Env version {conda_dict[x]}" for x in differing_versions]))
                logger.debug("\n")
                logger.info("To sync these versions:")
                logger.info(">>> conda ops env regenerate")
    elif len(conda_dict) > 0:
        check = False
        in_env = conda_dict.keys()
        logger.debug("\nThe following packages are in the environment but not in the lock file:\n")
        logger.debug(", ".join(in_env))
        logger.debug("\n")
        logger.info("To restore the environment to the state of the lock file")
        logger.info(">>> conda deactivate")
        logger.info(">>> conda ops env regenerate")
        logger.info(f">>> conda activate {env_name}")
        # logger.info(">>> conda ops sync")
    else:
        logger.debug("Pip packages in environment and lock file are in sync.\n")

    if die_on_error and not check:
        sys.exit(1)
    return check


def env_install(config=None):
    """
    Install the lockfile contents into the environment.

    This is *only* additive and does not delete existing packages form the environment.
    """
    if config is None:
        config = proj_load()

    env_name = config["settings"]["env_name"]
    explicit_lock_file = config["paths"]["explicit_lockfile"]
    explicit_files = generate_explicit_lock_files(config)

    logger.info(f"Installing lockfile into the environment {env_name}")
    with CondaOpsManagedCondarc(config["paths"]["condarc"]):
        conda_args = ["--prefix", get_prefix(env_name), "--file", str(explicit_lock_file)]
        stdout, stderr, result_code = run_command("install", conda_args, use_exception_handler=True)
        if result_code != 0:
            logger.error(stdout)
            logger.error(stderr)
            sys.exit(result_code)
    logger.info(stdout)

    pip_lock_file = config["paths"]["pip_explicit_lockfile"]
    if pip_lock_file in explicit_files:
        # Workaround for the issue in conda version 23.5.0 (and greater?) see issues.
        # We need to capture the pip install output to get the exact filenames of the packages
        with CondaOpsManagedCondarc(config["paths"]["condarc"]):
            stdout_backup = sys.stdout
            sys.stdout = capture_output = StringIO()
            with redirect_stdout(capture_output):
                conda_args = ["--prefix", get_prefix(env_name), "pip", "install", "-r", str(pip_lock_file), "--verbose"]
                stdout, stderr, result_code = run_command("run", conda_args, use_exception_handler=True)
                if result_code != 0:
                    logger.error(stdout)
                    logger.error(stderr)
            sys.stdout = stdout_backup
            stdout_str = capture_output.getvalue()
            logger.info(stdout_str)


def env_delete(config=None, env_name=None):
    """
    Deleted the conda ops managed conda environment (aka. conda remove -n env_name --all)
    """
    if env_name is None:
        env_name = config["settings"]["env_name"]

    env_exists = check_env_exists(env_name)
    if not env_exists:
        logger.warning(f"The conda environment {env_name} does not exist, and cannot be deleted.")
        logger.info("To create the environment:")
        logger.info(">>> conda ops env create")
        # logger.info(">>> conda ops create")
    if check_env_active(env_name):
        logger.warning(f"The conda environment {env_name} is active, and cannot be deleted.")
        logger.info("To deactivate the environment:")
        logger.info(">>> conda deactivate")
    else:
        logger.debug(f"Deleting the conda environment {env_name}")
        # no context handling needed to delete an environment
        stdout, stderr, result_code = run_command("remove", "--prefix", get_prefix(env_name), "--all", use_exception_handler=True)
        if result_code != 0:
            logger.error(stdout)
            logger.error(stderr)
            sys.exit(result_code)


def env_regenerate(config=None, env_name=None, lock_file=None):
    """
    Delete the environment and regenerate from a lock file.
    """
    if lock_file is None:
        lock_file = config["paths"]["lockfile"]
    if env_name is None:
        env_name = config["settings"]["env_name"]

    if check_env_active(env_name):
        logger.error(f"The environment {env_name} to be regenerated is active. Deactivate and try again.")
        logger.info(">>> conda deactivate")
        sys.exit(1)

    env_delete(config=config, env_name=env_name)
    env_create(config=config, env_name=env_name, lock_file=lock_file)


############################################
#
# Helper Functions
#
############################################


def json_to_explicit(json_list, package_manager="conda"):
    """
    Convert a json lockfile to the explicit string format that
    can be used for create and update conda environments.
    """
    explicit_str = ""
    for package in json_list:
        if package["manager"] == "conda" == package_manager:
            explicit_str += package["url"] + "\n"
        if package["manager"] == "pip" == package_manager:
            if "url" in package.keys() and "sha256" in package.keys():
                explicit_str += " ".join([package["name"], "@", package["url"], f"--hash=sha256:{package['sha256']}"]) + "\n"
            else:
                logger.error(
                    f"Unimplemented: package {package} does not have the required information \
                    for the explicit lockfile. It likely came from a local or vcs pip installation."
                )
    return explicit_str


def generate_explicit_lock_files(config=None, lock_file=None):
    """
    Generate an explicit lock files from the usual one (aka. of the format generated by `conda list --explicit`
    for conda and `package_name @ URL --hash=sha256:hash_value` for pip
    """
    logger.debug("Creating explicit lock file(s)")
    if lock_file is None:
        lock_file = config["paths"]["lockfile"]

    with open(lock_file, "r", encoding="utf-8") as jsonfile:
        json_reqs = json.load(jsonfile)

    # conda lock file
    explicit_str = "# This file may be used to create an environment using:\n\
    # $ conda create --name <env> --file <this file>\n@EXPLICIT\n"
    explicit_str += json_to_explicit(json_reqs, package_manager="conda")

    explicit_lock_file = config["paths"]["explicit_lockfile"]
    with open(explicit_lock_file, "w", encoding="utf-8") as explicitfile:
        explicitfile.write(explicit_str)

    # pypi lock file
    pip_reqs = json_to_explicit(json_reqs, package_manager="pip")
    if len(pip_reqs) > 0:
        pip_lock_file = config["paths"]["pip_explicit_lockfile"]
        with open(pip_lock_file, "w", encoding="utf-8") as explicitfile:
            explicitfile.write(pip_reqs)
        return [explicit_lock_file, pip_lock_file]
    return [explicit_lock_file]


def get_pypi_package_info(package_name, version, filename):
    """
    Get the pypi package information from pypi for a package name.

    If installed, use the matching distribution and platform information from what is installed.
    """
    url = f"https://pypi.org/pypi/{package_name}/{version}/json"

    # Fetch the package metadata JSON
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
    except Exception as exception:
        print(exception)
        logger.error(f"No releases found for url {url}")
        return None, None

    # Find the wheel file in the list of distributions
    releases = data["urls"]

    matching_releases = []
    for release in releases:
        if release["filename"] == filename:
            matching_releases.append(release)

    if matching_releases:
        for release in matching_releases:
            sha256_hash = release["digests"]["sha256"]
            url = release["url"]
            logger.debug(f"   The url for the file {filename} of {package_name} {version} is: {url}")
    else:
        logger.debug(f"No wheel distribution found for {package_name} {version}.")
        return None, None
    return url, sha256_hash


def extract_pip_installed_filenames(stdout, config=None):
    """
    Take the output of pip install --verbose to get the package name, version and filenames of what was installed.
    """
    list_stdout = re.split(r"Collecting |Requirement already ", stdout)

    filename_dict = {}
    for package_stdout in list_stdout[1:]:
        if "Using pip" in package_stdout:
            pass
        if "Using cached" in package_stdout:
            pattern = r"^(\S+)"
            match = re.search(pattern, package_stdout, re.MULTILINE)
            if match:
                requirement = Requirement(match.group(1))
                package_name = requirement.name
            else:
                package_name = None
                logger.error("No match for package_name found.")

            pattern = r"Using cached ([^\s]+)"
            match = re.search(pattern, package_stdout)
            if match:
                filename = match.group(1)
            else:
                filename = None
                logger.error("No match for filename found.")
            if filename is not None:
                version = filename.split("-")[1]
            else:
                version = None
            if version is not None:
                url, sha = get_pypi_package_info(package_name, version, filename)
            else:
                url = None
                sha = None
            filename_dict[package_name] = {"version": version, "filename": filename, "url": url, "sha256": sha}
        elif "satisfied: " in package_stdout:
            # in this case, look in existing lockfile for details
            pattern = r"satisfied: ([^\s]+)"
            match = re.search(pattern, package_stdout)
            if match:
                requirement = Requirement(match.group(1))
                package_name = requirement.name
            else:
                package_name = None
                logger.error("No match for package_name found.")
            lockfile = config["paths"]["lockfile"]
            with open(lockfile, "r", encoding="utf-8") as jsonfile:
                lock_list = json.load(jsonfile)
            for package in lock_list:
                if package["name"] == package_name:
                    filename_dict[package_name] = {
                        "version": package.get("version", None),
                        "filename": package.get("filename", None),
                        "url": package.get("url", None),
                        "sha256": package.get("sha256", None),
                    }
                    break
        elif "Downloading" in package_stdout:
            pattern = r"^(\S+)"
            match = re.search(pattern, package_stdout, re.MULTILINE)
            if match:
                requirement = Requirement(match.group(1))
                package_name = requirement.name
            else:
                package_name = None
                logger.error("No match for package_name found.")

            pattern = r"Downloading ([^\s]+)"
            match = re.search(pattern, package_stdout)
            if match:
                filename = match.group(1)
            else:
                filename = None
                logger.error("No match for filename found.")
            if filename is not None:
                version = filename.split("-")[1]
            else:
                version = None
            if version is not None:
                url, sha = get_pypi_package_info(package_name, version, filename)
            else:
                url = None
                sha = None
            filename_dict[package_name] = {"version": version, "filename": filename, "url": url, "sha256": sha}
        else:
            logger.error("Unimplemented so far...")
            logger.debug(package_stdout)
    return filename_dict


def get_prefix(env_name):
    """
    When conda is in an environment, the prefix gets computed on top of the active environment prefix which
    leads to odd behavious. Determine the prefix to use and pass that instead.
    """
    conda_info = get_conda_info()
    active_prefix = conda_info["active_prefix"]
    env_dirs = conda_info["envs_dirs"]
    if Path(env_dirs[0]) == Path(active_prefix) / "envs":
        split = str(env_dirs[0]).split("envs")
        prefix = Path(split[0]) / "envs"
    else:
        prefix = Path(env_dirs[0])
    return str(prefix / env_name)


def check_env_exists(env_name):
    """
    Given the name of a conda environment, check if it exists
    """
    json_output = get_conda_info()

    env_list = [Path(x).name for x in json_output["envs"]]
    return env_name in env_list


def check_env_active(env_name):
    """
    Given the name of a conda environment, check if it is active
    """
    conda_info = get_conda_info()
    active_env = conda_info["active_prefix_name"]

    return active_env == env_name
