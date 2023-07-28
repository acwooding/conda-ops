import json

from collections import defaultdict
from pathlib import Path

from .utils import yaml


def env_split(conda_env, conda_channel_order):
    """Given a conda_environment dict, and a channel order, split into versions for each channel.

    Returns:

    conda_env: (list)
       remaining setup bits of the environment.yml file
    channel_dict: (dict)
       dict containing the list of dependencies by channel name

        Python object corresponding to environment.yml"""
    # Cheater way to make deep Copies
    json_copy = json.dumps(conda_env)
    conda_env = json.loads(json_copy)

    deplist = conda_env.pop("dependencies")
    channel_dict = defaultdict(list)

    for k, dep in enumerate(deplist[:]):  # Note: copy list, as we mutate it
        if isinstance(dep, dict):  # nested yaml
            if dep.get("pip", None):
                pip_dict = deplist.pop(k)
                channel_dict["pip"] = pip_dict["pip"]
        else:
            prefix_check = dep.split("::")
            if len(prefix_check) > 1:
                channel = prefix_check[0]
                if channel not in conda_channel_order:
                    raise Exception(
                        f"the channel {channel} required for {dep} is not specified in a channel-order \
                        section of the environment file"
                    )
                channel_dict[f"{channel}"].append(prefix_check[1])
                deplist.remove(dep)

    channel_dict["defaults"] = deplist
    conda_env.pop("channel-order")
    return conda_env, channel_dict


def get_conda_channel_order(conda_env):
    """
    Given a conda_environment dict, get the channels from the channel order.
    """
    channel_order = conda_env.get("channel-order")

    if channel_order is None:
        channel_order = ["defaults"]
    if "defaults" not in channel_order:
        channel_order.insert(0, "defaults")
    return channel_order


def create_split_files(file_to_split, base_path, split_pip=True):
    """
    Given an environment.yml file to split, output the split files to the base_path.

    If split_pip, separate normal pypi packages from sdists and -e . packages.
    """
    with open(file_to_split, "r") as yamlfile:
        conda_env = yaml.load(yamlfile)

    base_path = Path(base_path)

    # check for acceptable formats
    channel_order = get_conda_channel_order(conda_env)

    _, channel_dict = env_split(conda_env, channel_order)

    for kind in channel_order + ["pip"]:
        if kind == "pip":
            if split_pip:
                sdist_list = []
                pypi_list = []
                for package in channel_dict["pip"]:
                    if package.startswith("-e") or ("/" in package):
                        sdist_list.append(package)
                    else:
                        pypi_list.append(package)
                if len(pypi_list) > 0:
                    filename = ".ops.pypi-requirements.txt"
                    with open(base_path / filename, "w") as file_handle:
                        file_handle.write("\n".join(pypi_list))
                    channel_order += ["pypi"]
                if len(sdist_list) > 0:
                    filename = ".ops.sdist-requirements.txt"
                    with open(base_path / filename, "w") as file_handle:
                        file_handle.write("\n".join(sdist_list))
                    channel_order += ["sdist"]
            else:
                filename = ".ops.pip-requirements.txt"
                with open(base_path / filename, "w") as file_handle:
                    file_handle.write("\n".join(channel_dict["pip"]))
        else:
            filename = f".ops.{kind}-environment.txt"
            with open(base_path / filename, "w") as file_handle:
                file_handle.write("\n".join(channel_dict[kind]))

    with open(base_path / ".ops.channel-order.include", "w") as file_handle:
        file_handle.write(" ".join(channel_order))
