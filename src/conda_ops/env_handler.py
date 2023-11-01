from contextlib import AbstractContextManager
import json
import os
from pathlib import Path


from .python_api import run_command


class CondaOpsManagedCondarc(AbstractContextManager):
    """
    Wrapper for calls to conda that set and unset the CONDARC value to the rc_path value.

    Since conda-ops track config settings that matter for the solver (solver and channel configuartion)
    including pip_interop_enabled, we use the context handler for the following conda commands:
    * conda create
    * conda install
    * conda list (it gives us conda and pip packages)
    * conda remove/uninstall (except remove --all)
    * conda run pip <any pip command>
    """

    def __init__(self, rc_path):
        self.rc_path = str(rc_path)

    def __enter__(self):
        self.old_condarc = os.environ.get("CONDARC")
        if Path(self.rc_path).exists():
            os.environ["CONDARC"] = self.rc_path
        else:
            logger.error("Conda ops managed .condarc file does not exist")
            logger.info("To create the managed .condarc file:")
            logger.info(">>> conda ops config create")
            sys.exit(1)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.old_condarc is not None:
            os.environ["CONDARC"] = self.old_condarc
        else:
            del os.environ["CONDARC"]
        if exc_type is SystemExit:
            logger.error("System Exiting...")
            logger.debug(f"exc_value: {exc_value} \n")
            logger.debug(f"exc_traceback: {traceback.print_tb(exc_traceback)}")


class EnvObject(object):
    def __init__(self, env_name=None, prefix=None, env_dir=None, **kwargs):
        self.name = env_name
        self.env_dir = env_dir
        if prefix is None and env_name is not None:
            self.prefix = get_prefix(env_name)
        elif len(prefix) < 1 and env_name is not None:
            self.prefix = get_prefix(env_name)
        elif not Path(prefix).exists() and self.env_dir is not None:
            self.prefix = str(Path(self.env_dir) / Path(prefix))
        else:
            self.prefix = str(prefix)

    def exists(self):
        """
        Given the conda name or prefix of environment, check if it exists
        """
        json_output = get_conda_info()

        env_list = [Path(x) for x in json_output["envs"]]
        env_prefix = Path(self.prefix).resolve()
        return env_prefix in env_list

    def active(self):
        """
        Given the conda environment, check if it is active
        """
        conda_info = get_conda_info()
        active_env = conda_info["active_prefix"]
        return active_env == self.prefix

    @property
    def display_name(self):
        """
        Return env name if it is in use, and the fully qualified prefix otherwise.
        """
        if self.name is None:
            return Path(self.prefix).resolve()
        elif len(self.name) < 1:
            return Path(self.prefix).resolve()
        else:
            return self.name

    @property
    def relative_display_name(self):
        """
        Return the prefix relative to the cwd if it is a subdir of .conda_ops, otherwise return the env_name.
        """
        p = Path(self.prefix).resolve()
        if self.env_dir is not None:
            try:
                rel_p = p.relative_to(self.env_dir)
            except Exception:
                rel_p = None
            if rel_p is not None:
                cwd = Path.cwd()
                try:
                    return p.relative_to(cwd)
                except Exception:
                    return p
            else:
                return self.name
        else:
            return self.name


def get_conda_info():
    """Get conda configuration information.

    XXX Should this maybe look into the conda internals instead?
    XXX previous get_info_dict did this, but the internal call does not contain the envs
    """
    # Note: we do not want or need to use the condarc context handler here.
    stdout, stderr, result_code = run_command("info", "--json", use_exception_handler=False)
    if result_code != 0:
        logger.info(stdout)
        logger.info(stderr)
        sys.exit(result_code)
    return json.loads(stdout)


def get_prefix(env_name):
    """
    When conda is in an environment, the prefix gets computed on top of the active environment prefix which
    leads to odd behaviour. Determine the prefix to use and pass that instead.
    """
    conda_info = get_conda_info()
    active_prefix = conda_info["active_prefix"]
    env_dirs = conda_info["envs_dirs"]
    prefix = None
    for env_dir in env_dirs:
        env_dir_path = Path(env_dir)
        if active_prefix is not None:
            if env_dir_path == Path(active_prefix) / "envs":
                split = str(env_dir).split("envs")
                prefix = Path(split[0]) / "envs"
                break
        if env_dir_path.exists() and os.access(env_dir_path, os.W_OK):
            prefix = env_dir_path
            break
    if prefix is None:
        logger.error(f"Permission error for all available conda envs directories: {env_dirs}. Check your conda config settings.")
        sys.exit(1)
    else:
        return str(prefix / env_name)


def check_env_exists(env_name=None, prefix=None):
    """
    Given the name of a conda environment, check if it exists
    """
    json_output = get_conda_info()

    env_list = [Path(x) for x in json_output["envs"]]
    if prefix is None:
        prefix = Path(get_prefix(env_name))
    else:
        prefix = Path(prefix)
    return prefix in env_list


def check_env_active(env_name):
    """
    Given the name of a conda environment, check if it is active
    """
    conda_info = get_conda_info()
    active_env = conda_info["active_prefix_name"]

    return active_env == env_name
