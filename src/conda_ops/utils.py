import logging

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


def align_and_print_packages(packages, header=("Package Name", "Version", "Channel", "Arch", "Build")):
    sorted_data = sorted(packages[:], key=lambda x: x[0])
    # Define the column widths based on the maximum length in each column
    column_widths = [max(len(str(item)) for item in column) + 2 for column in zip(*sorted_data)]

    # Print the header
    header_row = " ".join(str(item).ljust(width) for item, width in zip(header, column_widths))
    table_str = "\n" + header_row + "\n"
    table_str += "========================================================\n"

    # Print the data rows
    for row in sorted_data[:]:
        formatted_line = " ".join(str(item).ljust(width) for item, width in zip(row, column_widths))
        table_str += formatted_line + "\n"

    table_str += "\n"
    return table_str
