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
