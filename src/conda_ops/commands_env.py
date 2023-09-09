import json
from pathlib import Path
import subprocess
import sys
from io import StringIO
from contextlib import redirect_stdout

from .python_api import run_command
from .commands_proj import proj_load, get_conda_info, CondaOpsManagedCondarc
from .conda_config import env_pip_interop
from .commands_lockfile import lockfile_check
from .requirements import LockSpec, PackageSpec
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

    for explicit_file in explicit_files:
        explicit_lock_file = config["paths"]["explicit_lockfile"]
        if str(explicit_file) == str(explicit_lock_file):
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
        else:
            logger.info("Installing pip managed dependencies...")

            # Workaround for the issue in conda version 23.5.0 (and greater?) see issues.
            # We need to capture the pip install output to get the exact filenames of the packages
            with CondaOpsManagedCondarc(config["paths"]["condarc"]):
                stdout_backup = sys.stdout
                sys.stdout = capture_output = StringIO()
                with redirect_stdout(capture_output):
                    conda_args = ["--prefix", get_prefix(env_name), "pip", "install", "-r", str(explicit_file), "--verbose", "--no-cache"]
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
    new_json_reqs = []
    for package in json_reqs:
        conda_spec = LockSpec.from_conda_list(package)
        if conda_spec.channel == "pypi" or conda_spec.channel == "<develop>":
            package["manager"] = "pip"
            if pip_dict is not None:
                pip_dict_entry = pip_dict.get(conda_spec.name, None)
                if pip_dict_entry is not None:
                    pip_dict_entry["name"] = conda_spec.name
                    pip_dict_entry["channel"] = conda_spec.channel
                    pip_spec = LockSpec(pip_dict_entry)
                    if pip_spec.version != conda_spec.version:
                        logger.error(
                            f"The pip extra info entry version {pip_spec.version} does \
                            not match the conda package version {conda_spec.version}"
                        )
                        sys.exit(1)
                    else:
                        new_json_reqs.append(pip_spec.info_dict)
                else:
                    logger.error(f"No pip dict entry for {conda_spec.name}")
                    new_json_reqs.append(conda_spec.info_dict)
            else:
                logger.error("No pip_dict present")
                new_json_reqs.append(conda_spec.info_dict)
        else:
            starter_str = "/".join([package["base_url"], package["platform"], package["dist_name"]])
            line = None
            for line in explicit:
                if starter_str in line:
                    break
            if line:
                conda_spec.add_conda_explicit_info(line)
            new_json_reqs.append(conda_spec.info_dict)

    blob = json.dumps(new_json_reqs, indent=2, sort_keys=True)
    with open(lock_file, "w", encoding="utf-8") as jsonfile:
        jsonfile.write(blob)

    return new_json_reqs


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


def pip_step_env_lock(channel, config, env_name=None, extra_pip_dict=None):
    """
    Update the environment with the pip requirements and generate a new lock file.
    """
    # set the pip interop flag to True as soon as pip packages are to be installed so conda remain aware of it
    # possibly set this at the first creation of the environment so it's always True

    if env_name is None:
        env_name = config["settings"]["env_name"]

    env_pip_interop(config=config, flag=True)

    ops_dir = config["paths"]["ops_dir"]
    temp_pip_file = ops_dir / ".temp_pip_report.json"
    logger.info(f"Generating the intermediate lock file for pip via environment {env_name}")

    reqs_file = ops_dir / f".ops.{channel}-requirements.txt"

    # Workaround for the issue in cconda version 23.5.0 (and greater?) see issues.
    # We need to capture the pip install output to get the exact filenames of the packages
    with CondaOpsManagedCondarc(config["paths"]["condarc"]):
        stdout_backup = sys.stdout
        sys.stdout = capture_output = StringIO()
        with redirect_stdout(capture_output):
            conda_args = ["--prefix", get_prefix(env_name), "pip", "install", "-r", str(reqs_file), "--no-cache", "--report", f"{temp_pip_file}"]
            stdout, stderr, result_code = run_command("run", conda_args, use_exception_handler=True)
            if result_code != 0:
                logger.error(stdout)
                logger.error(stderr)
                return None
        sys.stdout = stdout_backup
        stdout_str = capture_output.getvalue()
        print(stdout_str)

    pip_dict = extract_pip_info(temp_pip_file, config=config)

    # append extra information to pass on if it exists
    if extra_pip_dict is not None:
        for key, value in extra_pip_dict.items():
            if pip_dict.get(key, None) is None:
                pip_dict[key] = value

    channel_lockfile = ops_dir / f".ops.lock.{channel}"
    json_reqs = env_lock(config, lock_file=channel_lockfile, env_name=env_name, pip_dict=pip_dict)

    return json_reqs, pip_dict


def env_check(config=None, die_on_error=True):
    """
    Check that the conda ops environment exists. Warn (but don't fail) if it is not active.
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
        logger.warning("Lock file is missing or inconsistent.")
        logger.warning("Cannot determine the consistency of the lockfile and environment.")
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
        logger.warning("Environment does not exist.")
        logger.error("Cannot determine the consistency of the lockfile and environment.")

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
    logger.info(f"Found {len(conda_set)} conda package(s) in environment: {env_name}")

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
            logger.info("\nThe following packages are in the environment but not in the lock file:\n")
            logger.info("\n".join(in_env))
            logger.info("\n")
            logger.info("To restore the environment to the state of the lock file")
            logger.info(">>> conda deactivate")
            logger.info(">>> conda ops env regenerate")
            logger.info(f">>> conda activate {env_name}")
            # logger.info(">>> conda ops sync")
        if len(in_lock) > 0:
            logger.info("\nThe following packages are in the lock file but not in the environment:\n")
            logger.info("\n".join(in_lock))
            logger.info("\n")
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
        if package["channel"] in ["pypi", "<develop>"]:
            conda_dict[package["name"]] = package["version"]

    logger.info(f"Found {len(conda_dict)} pip package(s) in environment: {env_name}")

    if len(explicit_files) > 1:
        env_pip_interop(config=config, flag=True)

        logger.debug("Checking consistency of pip installed packages...")
        lock_dict = {}
        lockfile = config["paths"]["lockfile"]
        with open(lockfile, "r", encoding="utf-8") as jsonfile:
            lock_list = json.load(jsonfile)
        for package in lock_list:
            if package["manager"] == "pip":
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
            differing_versions = {key: (value, lock_dict[key]) for key, value in conda_dict.items() if key in lock_dict and value != lock_dict[key]}
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
    for explicit_file in explicit_files:
        explicit_lock_file = config["paths"]["explicit_lockfile"]
        if str(explicit_file) == str(explicit_lock_file):
            with CondaOpsManagedCondarc(config["paths"]["condarc"]):
                conda_args = ["--prefix", get_prefix(env_name), "--file", str(explicit_lock_file)]
                stdout, stderr, result_code = run_command("install", conda_args, use_exception_handler=True)
                if result_code != 0:
                    logger.error(stdout)
                    logger.error(stderr)
                    sys.exit(result_code)
            print(stdout)
        else:
            logger.info("Installing pip packages into the environment")
            # Workaround for the issue in conda version 23.5.0 (and greater?) see issues.
            # We need to capture the pip install output to get the exact filenames of the packages
            with CondaOpsManagedCondarc(config["paths"]["condarc"]):
                stdout_backup = sys.stdout
                sys.stdout = capture_output = StringIO()
                with redirect_stdout(capture_output):
                    conda_args = ["--prefix", get_prefix(env_name), "pip", "install", "-r", str(explicit_file), "--verbose", "--no-cache"]
                    stdout, stderr, result_code = run_command("run", conda_args, use_exception_handler=True)
                    if result_code != 0:
                        logger.error(stdout)
                        logger.error(stderr)
                        sys.exit(result_code)
                sys.stdout = stdout_backup
                stdout_str = capture_output.getvalue()
                print(stdout_str)


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


def json_to_explicit(json_list, package_manager="conda", hash_exists=True):
    """
    Convert a json lockfile to the explicit string format that
    can be used for create and update conda environments.

    hash_exists only matters for the pip package_manager
    """
    explicit_str = ""
    for package in json_list:
        lock_package = LockSpec(package)
        if lock_package.check_consistency():
            if lock_package.manager == package_manager:
                if hash_exists == lock_package.hash_exists:
                    explicit_str += lock_package.to_explicit() + "\n"
        else:
            logger.error("Failed to convert json to explicit lock file")
            sys.exit(1)
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
    explicit_str += json_to_explicit(json_reqs, package_manager="conda", hash_exists=True)

    explicit_lock_file = config["paths"]["explicit_lockfile"]
    with open(explicit_lock_file, "w", encoding="utf-8") as explicitfile:
        explicitfile.write(explicit_str)
    lockfiles = [explicit_lock_file]

    # pypi lock file
    for hash_exists in [True, False]:
        pip_reqs = json_to_explicit(json_reqs, package_manager="pip", hash_exists=hash_exists)
        if len(pip_reqs) > 0:
            if hash_exists:
                pip_lock_file = config["paths"]["pip_explicit_lockfile"]
            else:
                pip_lock_file = config["paths"]["nohash_explicit_lockfile"]
            with open(pip_lock_file, "w", encoding="utf-8") as explicitfile:
                explicitfile.write(pip_reqs)
            lockfiles.append(pip_lock_file)
    return lockfiles


def extract_pip_info(json_input, config=None):
    """
    Take the json output from a pip install --report command and extract the relevant information.
    json_input can be a filename, path or
    """
    if isinstance(json_input, str):
        pip_info = json.loads(json_input)
    elif Path(json_input).exists():
        with open(json_input, "r", encoding="utf-8") as json_handle:
            pip_info = json.load(json_handle)
    else:
        logger.error(f"Unrecognized input format: {json_input}")
        sys.exit(1)

    package_dict = {}
    for package in pip_info["install"]:
        p_info = LockSpec.from_pip_report(package)
        package_dict[p_info.conda_name] = p_info.info_dict
    return package_dict


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

    env_list = [Path(x) for x in json_output["envs"]]
    env_prefix = Path(get_prefix(env_name))
    return env_prefix in env_list


def check_env_active(env_name):
    """
    Given the name of a conda environment, check if it is active
    """
    conda_info = get_conda_info()
    active_env = conda_info["active_prefix_name"]

    return active_env == env_name
