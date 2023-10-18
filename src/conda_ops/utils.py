import logging
import os
import re

from ruamel.yaml import YAML

yaml = YAML()
yaml.default_flow_style = False
yaml.width = 4096
yaml.indent(offset=4)


logger = logging.getLogger()

conda_logger = logging.getLogger("conda.cli.python_api")
conda_logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s %(name)-15s %(levelname)-8s %(processName)-10s %(message)s"))
conda_logger.addHandler(ch)

sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter(" %(levelname)-8s (%(name)s) %(message)s"))
logger.addHandler(sh)

CONDA_OPS_DIR_NAME = ".conda-ops"
CONFIG_FILENAME = "config.ini"


def align_and_print_data(data, header=None):
    """
    Align and print a list of data in a printable tabular format (returns a string).
    """
    if header is None:
        header = data[0]
        data = data[1:]
    sorted_data = sorted(data[:], key=lambda x: x[0])
    # Define the column widths based on the maximum length in each column
    column_widths = [max(len(str(item)) for item in column) + 2 for column in zip(*([header] + sorted_data))]

    # Print the header
    header_row = " ".join(str(item).ljust(width) for item, width in zip(header, column_widths))
    table_str = "\n\n" + header_row + "\n"
    table_str += "=" * len(header_row) + "\n"

    # Print the data rows
    for row in sorted_data[:]:
        formatted_line = " ".join(str(item).ljust(width) for item, width in zip(row, column_widths))
        table_str += formatted_line + "\n"

    table_str += "\n"
    return table_str


def is_url_requirement(requirement):
    is_url = False
    if "-e " in requirement:
        is_url = True
    if requirement.startswith(".") or requirement.startswith("~") or re.match(r"^\w+:\\", requirement) is not None or os.path.isabs(requirement) or "/" in requirement:
        is_url = True
    for protocol in ["+ssh:", "+file:", "+https:"]:
        if protocol in requirement:
            is_url = True
    return is_url
