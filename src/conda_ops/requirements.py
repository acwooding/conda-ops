import json
import re
import sys
import urllib

from packaging.requirements import Requirement
from conda.common.pkg_formats.python import pypi_name_to_conda_name, norm_package_name
from conda.models.match_spec import MatchSpec

from .utils import logger, is_url_requirement
from .commands_proj import proj_load
from .kvstore import KVStore


class PackageSpec:
    def __init__(self, spec, manager=None, channel=None):
        self.spec = spec
        if manager is None:
            if channel is not None:
                if channel == "pip":
                    manager = channel
                else:
                    manager = "conda"
            else:
                if "pip::" in spec:
                    manager = "pip"
                    channel = "pip"
                else:
                    manager = "conda"
        self.manager = manager
        self.requirement, self.editable = self.parse_requirement(spec, manager, channel=channel)

    @staticmethod
    def parse_requirement(spec, manager, channel=None):
        editable = False
        clean_spec = spec.strip()
        if len(clean_spec.split("::")) > 2:
            logger.error(clean_spec)
        if channel is not None:
            if "::" in spec:
                # check channel is consistent
                spec_channel = clean_spec.split("::")[0]
                if spec_channel != channel:
                    logger.warning(f"The requirement {spec} does not match the specified channel {channel}")
            elif manager == "conda":
                clean_spec = f"{channel}::{clean_spec}"
        if manager == "conda":
            if "-e " in clean_spec:
                logger.error(f"Spec {clean_spec} seems to be editable")
                logger.error("Editable modules must use the pip channel")
                logger.info("To use pip with reqs add, use '--pip'")
            requirement = MatchSpec(clean_spec)

        elif manager == "pip":
            if "-e " in clean_spec:
                editable = True
                clean_spec = clean_spec.split("-e ")[1]
            if "pip::" in clean_spec:
                clean_spec = clean_spec.split("pip::")[1]
            # look for "=" and not "==" in spec
            # "=" is a valid specifier in conda that doesn't mean ==
            # but pip only accepts ==
            pattern = r"^\s*([\w.-]+)\s*=\s*([\w.-]+)\s*$"
            match = re.match(pattern, clean_spec)
            if match:
                # Change = to ==
                clean_spec = clean_spec.replace("=", "==").strip()
            if is_url_requirement(clean_spec):
                requirement = PathSpec(clean_spec)
            else:
                requirement = Requirement(clean_spec)
        return requirement, editable

    @classmethod
    def from_conda_url(cls, url):
        """
        Create a PackageSpec object from a conda url.
        """
        return cls(spec=url, manager="conda", channel=None)

    @property
    def name(self):
        return self.requirement.name

    @property
    def conda_name(self):
        if self.manager == "pip":
            return pypi_name_to_conda_name(norm_package_name(self.name))
        return self.name

    @property
    def version(self):
        if self.manager == "pip":
            return self.requirement.specifier
        return self.requirement.version

    @property
    def channel(self):
        if self.manager == "pip":
            return self.manager
        else:
            full_channel = self.requirement.get("channel")
            if full_channel is None:
                return "defaults"
            else:
                return full_channel.name

    @property
    def is_pathspec(self):
        return isinstance(self.requirement, PathSpec)

    def __str__(self):
        if self.editable:
            return "-e " + str(self.requirement)
        return str(self.requirement)

    def to_reqs_entry(self):
        if self.editable:
            return str(self)
        elif self.channel == "defaults":
            string_rep = str(self.requirement)
            if "::" in string_rep:
                return string_rep.split("::")[1]
            else:
                return string_rep
        else:
            return str(self.requirement)

    def to_status_info(self):
        """
        Information for display in conda ops status calls
        """
        if self.manager == "conda":
            name_str = f"{self.name}"
            channel_str = f"{self.channel}"
            subdir_str = f"{self.requirement.get('subdir')}"
            version_str = f"{self.version}"
            build_str = f"{self.requirement.get('build')}"
        return name_str, version_str, channel_str, subdir_str, build_str


class PathSpec:
    def __init__(self, spec):
        self.spec = spec

    def __str__(self):
        return self.spec

    @property
    def name(self):
        return None

    @property
    def version(self):
        return None


class LockSpec:
    def __init__(self, info_dict):
        self.info_dict = info_dict

    @classmethod
    def from_pip_report(cls, pip_dict, platform=None):
        """
        Parses the output from and entry in 'pip install --report' to get desired fields
        """
        download_info = pip_dict.get("download_info", None)
        if download_info is None:
            url = None
            sha = None
        else:
            if "vcs_info" in download_info.keys():
                vcs = download_info["vcs_info"]["vcs"]
                raw_url = download_info["url"]
                if vcs == "git":
                    url = vcs + "+" + raw_url + "@" + download_info["vcs_info"]["commit_id"]
                else:
                    logger.warning(f"Unimplemented vcs {vcs}. Will work with the general url but not specify the revision.")
                    logger.info("To request support for your vcs, please file an issue.")
                    url = raw_url
            else:
                url = download_info["url"]

            archive_info = download_info.get("archive_info", None)
            if archive_info is None:
                sha = None
            else:
                hashes = archive_info.get("hashes", None)
                hash_val = archive_info.get("hash", None)
                if hashes is not None:
                    sha = hashes["sha256"]
                elif hash_val is not None:
                    if "sha256=" in hash_val:
                        sha = hash_val.split("sha256=")[1]
                    else:
                        sha = None
                else:
                    sha = None
                if sha is None:
                    logger.error(f"No hash info found for {pip_dict['metadata']['name']} in {archive_info}")

            dir_info = download_info.get("dir_info", None)
            if dir_info is None:
                editable = False
            else:
                editable = dir_info.get("editable", False)
            name = pypi_name_to_conda_name(norm_package_name(pip_dict["metadata"]["name"]))
        info_dict = {
            "name": name,
            "manager": "pip",
            "channel": "pypi",
            "version": pip_dict["metadata"]["version"],
            "url": url,
            "hash": {"sha256": sha},
            "requested": pip_dict["requested"],
            "editable": editable,
            "pip_name": pip_dict["metadata"]["name"],
        }
        if platform is not None:
            info_dict["platform"] = platform
        return cls(info_dict)

    @classmethod
    def from_conda_list(cls, conda_dict, platform=None):
        """
        Parses the output from an entry in 'conda list --json' to get desired fields
        """
        info_dict = {"name": conda_dict["name"], "version": conda_dict["version"], "channel": conda_dict["channel"]}
        if conda_dict["channel"] in ["pypi", "<develop>"]:
            info_dict["manager"] = "pip"
        else:
            info_dict["manager"] = "conda"
        if platform is not None:
            info_dict["platform"] = platform
        return cls(info_dict)

    @classmethod
    def from_lock_entry(cls, lock_dict, config=None, lookup_file=None):
        lock_url = lock_dict.get("url", None)
        url = urllib.parse.urlparse(lock_url)
        if url.scheme == "local":
            url_lookup = load_url_lookup(config=config, lookup_file=lookup_file)
            try:
                lock_dict["url"] = url_lookup.get(url.netloc)
            except Exception:
                lock_dict["url"] = ""

        return cls(lock_dict)

    def add_conda_explicit_info(self, explicit_string):
        """
        Take an explicit string from `conda list --explicit --md5` and add the url and md5 fields
        """
        # check we're using a valid matching LockSpec
        if (self.manager != "conda") or (self.name not in explicit_string):
            logger.error(f"The explicit string {explicit_string} does not match the LockSpec {self}")
            sys.exit(1)
        md5_split = explicit_string.split("#")
        self.info_dict["hash"] = {"md5": md5_split[-1]}
        self.info_dict["url"] = md5_split[0]

    def check_consistency(self):
        check = True
        if self.manager == "conda":
            if self.url:
                # check the url consistency
                for key in ["name", "version", "channel"]:
                    value = self.info_dict.get(key, None)
                    if value:
                        if value not in self.url:
                            logger.error(f"Url entry for package {self.name} is inconsistent")
                            logger.debug(f"{self.url}, {self.version}, {self.channel}")
                            check = False
        if self.channel:
            if self.manager == "pip" and self.channel not in ["pypi", "<develop>"]:
                check = False
                logger.error(f"Channel and manager entries for package {self.name} is inconsistent")
            if self.manager == "conda" and self.channel == "pypi":
                check = False
                logger.error(f"Channel and manager entries for package {self.name} is inconsistent")
        return check

    def to_explicit(self):
        """
        For entry into a pip or conda explicit lock file.
        """
        try:
            if self.manager == "conda":
                return self.url + "#" + self.md5_hash
            if self.manager == "pip":
                if self.hash_exists:
                    return " ".join([self.name, "@", self.url, f"--hash=sha256:{self.sha256_hash}"])
                elif not self.editable:
                    return " ".join([self.name, "@", self.url])
                else:
                    return " ".join(["-e", self.url])
        except Exception as e:
            logger.error(
                f"Unimplemented: package {self.name} does not have the required information \
                for the explicit lockfile. It likely came from a local or vcs pip installation."
            )
            print(e)
            print(self)
            return None

    @property
    def name(self):
        return self.info_dict["name"]

    @property
    def conda_name(self):
        if self.manager == "pip":
            return pypi_name_to_conda_name(norm_package_name(self.name))
        return self.name

    @property
    def version(self):
        return self.info_dict["version"]

    @property
    def manager(self):
        return self.info_dict["manager"]

    @property
    def url(self):
        return self.info_dict.get("url", None)

    @property
    def channel(self):
        return self.info_dict.get("channel", None)

    @property
    def platform(self):
        return self.info_dict.get("platform", None)

    @property
    def sha256_hash(self):
        hash_dict = self.info_dict.get("hash", None)
        if hash_dict:
            return hash_dict.get("sha256", None)
        return None

    @property
    def md5_hash(self):
        hash_dict = self.info_dict.get("hash", None)
        if hash_dict:
            return hash_dict.get("md5", None)
        return None

    @property
    def hash_exists(self):
        hash_dict = self.info_dict.get("hash", None)
        if hash_dict is not None:
            for key, value in hash_dict.items():
                if value is not None:
                    return True
        return False

    def to_lock_entry(self, config=None, lookup_file=None):
        """
        Create a lock entry for the LockSpec.

        Note that this modifies or adds an entry into the lookup_file
        """
        lock_entry = self.info_dict
        url = urllib.parse.urlparse(self.url)
        if url.scheme == "file":
            url_name = self.name
            url_lookup = load_url_lookup(config=config, lookup_file=lookup_file)
            url_lookup[url_name] = self.url
            lock_entry["url"] = f"local://{url_name}"
        return lock_entry

    @property
    def editable(self):
        return self.info_dict.get("editable", False)

    @editable.setter
    def editable(self, value):
        self.info_dict["editable"] = value

    def __str__(self):
        return str(self.info_dict)

    def __repr__(self):
        return repr(self.info_dict)


def load_url_lookup(config=None, lookup_file=None):
    """
    Load the lockfile path lookup.
    """
    if lookup_file is None:
        if config is None:
            config = proj_load()
        lookup_file = config["paths"].get("lockfile_url_lookup", None)
        if lookup_file is None:
            logger.error("Missing entry for lockfile_url_lookup in config.ini")
            logger.info("Regenerate the config.ini:")
            logger.info(">>> conda ops init")
            sys.exit(1)
    lookup = KVStore(config_file=lookup_file, config_section="LOCKFILE_URLS")
    return lookup


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
            releases = data["urls"]
    except Exception as exception:
        # try another url pattern if needed "https://pypi.org/pypi/{package_name}/json"
        print(exception)
        logger.error(f"No releases found for url {url}")
        return None, None

    # Find the wheel file in the list of distributions
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
