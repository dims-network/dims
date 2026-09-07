"""Console entry point for `dims-case`.

The command in tools/ is the same thing for someone working from a checkout;
both call dims_case.core, so they cannot drift apart.
"""
import os
import runpy
import sys


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    script = os.path.join(root, "tools", "dims-case")
    if not os.path.exists(script):
        sys.exit("dims-case: this command needs a checkout of dims-network/dims "
                 "(it copies the core into your study, so it needs the core).")
    sys.argv = ["dims-case"] + list(argv if argv is not None else sys.argv[1:])
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    main()
