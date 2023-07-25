import os
import re

from packaging.requirements import Requirement
from conda.models.match_spec import MatchSpec

from .utils import logger


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
                manager = "conda"
        self.manager = manager
        self.requirement, self.editable = self.parse_requirement(spec, manager)

    @staticmethod
    def parse_requirement(spec, manager):
        editable = False
        # look for "=" and not "==" in spec
        pattern = r"^\s*([\w.-]+)\s*=\s*([\w.-]+)\s*$"
        match = re.match(pattern, spec)
        if match:
            # Change = to ==
            clean_spec = spec.replace("=", "==").strip()
        else:
            clean_spec = spec.strip()

        if manager == "conda":
            requirement = MatchSpec(clean_spec)
        elif manager == "pip":
            if "-e " in clean_spec:
                editable = True
                clean_spec = clean_spec.split("-e ")[1]
            if is_path_requirement(clean_spec) or "git+https" in clean_spec:
                requirement = PathSpec(clean_spec)
            else:
                requirement = Requirement(clean_spec)
        return requirement, editable

    @property
    def name(self):
        return self.requirement.name

    @property
    def version(self):
        if self.manager == "pip":
            return self.requirement.specifier
        else:
            return self.requirement.version

    @property
    def is_pathspec(self):
        return type(self.requirement) == PathSpec

    def __str__(self):
        if self.editable:
            return "-e " + str(self.requirement)
        else:
            return str(self.requirement)


class PathSpec:
    def __init__(self, spec, editable=False):
        self.spec = spec
        logger.info(f"Does not check path/url requirements yet...assuming {spec} is valid")

    def __str__(self):
        return self.spec

    @property
    def name(self):
        return self.spec

    @property
    def version(self):
        return None


def is_path_requirement(requirement):
    # Check if the requirement starts with a file path indicator or is a local directory
    return requirement.startswith(".") or requirement.startswith("/") or requirement.startswith("~") or re.match(r"^\w+:\\", requirement) is not None or os.path.isabs(requirement)


class LockSpec:
    def __init__(self, info_dict):
        self.info_dict = info_dict

    @classmethod
    def from_pip_report(cls, pip_dict):
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
                if vcs == "git":
                    url = vcs + "+" + download_info["url"] + "@" + download_info["vcs_info"]["commit_id"]
                else:
                    logger.warning(f"Unimplemented vcs {vcs}. Will work with the general url but not specify the revision.")
                    logger.info("To request support for your vcs, please file an issue.")
                    url = download_info["url"]
            else:
                url = download_info["url"]

            archive_info = pip_dict["download_info"].get("archive_info", None)
            if archive_info is None:
                sha = None
            else:
                sha = archive_info["hashes"]["sha256"]

        info_dict = {"name": pip_dict["metadata"]["name"].lower(), "manager": "pip", "channel": "pypi", "version": pip_dict["metadata"]["version"], "url": url, "hash": {"sha256": sha}}
        return cls(info_dict)

    @classmethod
    def from_conda_list(cls, conda_dict):
        """
        Parses the output from an entry in 'conda list --json' to get desired fields
        """
        info_dict = {"name": conda_dict["name"], "version": conda_dict["version"], "channel": conda_dict["channel"]}
        if conda_dict["channel"] == "pypi":
            info_dict["manager"] = "pip"
        else:
            info_dict["manager"] = "conda"
        return cls(info_dict)

    def add_conda_explicit_info(self, explicit_string):
        """
        Take an explicit string from `conda list --explicit --md5` and add the url and md5 fields
        """
        # check we're using a valid matching LockSpec
        if self.manager != "conda" or not self.name in explicit_string:
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
            if self.manager == "pip" and self.channel != "pypi":
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
                return " ".join([self.name, "@", self.url, f"--hash=sha256:{self.sha256_hash}"])
        except Exception as e:
            logger.error(
                f"Unimplemented: package {self.name} does not have the required information \
                for the explicit lockfile. It likely came from a local or vcs pip installation."
            )
            print(e)

    @property
    def name(self):
        return self.info_dict["name"]

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

    def __str__(self):
        return str(self.info_dict)

    def __repr__(self):
        return repr(self.info_dict)
