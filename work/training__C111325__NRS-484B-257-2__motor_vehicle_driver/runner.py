"""Exact NRS 484B.257(2) Native runner entrypoint."""
import runpy

if __name__ == '__main__':
    runpy.run_module('nonthrough_native_capture', run_name='__main__')
