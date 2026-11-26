"""Exact NRS 484A.450(3) Native runner entrypoint."""

import runpy


if __name__ == "__main__":
    runpy.run_module("native_capture", run_name="__main__")
