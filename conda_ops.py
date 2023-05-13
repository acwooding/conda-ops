import argparse

from sympy import symbols
from sympy.plotting import textplot

import conda.plugins

# Directly modifies the example in https://github.com/conda/conda-plugin-template/tree/main/tutorials/subcommands/python which
# is available under the BSD 3-clause license: https://github.com/conda/conda-plugin-template/blob/main/LICENSE

def conda_ops(argv: list):
    parser = argparse.ArgumentParser("conda ops")

    parser.add_argument("x", type=float, help="First coordinate to graph")
    parser.add_argument("y", type=float, help="Second coordinate to graph")
    parser.add_argument("z", type=float, help="Third coordinate to graph")

    args = parser.parse_args(argv)

    s = symbols('s')
    textplot(s**args.x, args.y, args.z)


@conda.plugins.hookimpl
def conda_subcommands():
    yield conda.plugins.CondaSubcommand(
        name="ops",
        summary="A subcommand that takes three coordinates and prints out an ascii graph",
        action=conda_ops,
    )
