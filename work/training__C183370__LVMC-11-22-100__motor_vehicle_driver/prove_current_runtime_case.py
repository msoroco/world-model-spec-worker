"""Run a complete four-candidate cutover diagnostic for one selected case."""
import argparse
from prove_current_runtime_chain import prove

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    args = parser.parse_args()
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        prove(args.case, candidate)
