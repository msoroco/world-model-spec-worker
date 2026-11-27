"""Exact NRS 484B.503 Native passenger-curb acquisition entrypoint."""

import runpy


if __name__ == "__main__":
    runpy.run_module("native.native_capture", run_name="__main__")
