"""Pinned CPU stage, atom, measurement and negative-source diagnostics."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path[:0] = [str(REPO / 'runtime' / 'scenario_pipeline'), str(ROOT / 'tests')]

from worker_exchange.atom_preflight import check_required_atoms
from worker_exchange.measurement_contract import validate as validate_contract
from worker_exchange.measurement_contract import verify_report
from worker_exchange.semantic_delivery import validate as validate_semantic
from analysis import build_report
from test_analysis import write_attempt


def main():
    assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    suffixes = ('precedence', 'advance', 'other_later', 'signal_red')
    manifest = {'cases': [{'case_id': ROOT.name + '__' + suffix,
                           'construction': 'cases/' + suffix + '/construction.json'}
                          for suffix in suffixes]}
    semantic = validate_semantic(ROOT, assignment, manifest)
    analysis_code = (ROOT / 'analysis.py').read_text()
    contracts = []
    for suffix in suffixes:
        folder = ROOT / 'cases' / suffix
        config = json.loads((folder / 'config.json').read_text())
        check_required_atoms(REPO / 'runtime', config['required_atoms'],
                             config['source_packets'], config)
        contract = json.loads((folder / 'measurement-contract.json').read_text())
        validate_contract(contract, plan['requirement_dispositions'],
                          analysis_code, ROOT.name + '__' + suffix)
        contracts.append(contract)
    scratch = REPO / '.runtime-work'
    scratch.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=scratch) as temporary:
        fixture = Path(temporary)
        write_attempt(fixture)
        report = build_report(fixture)
        outputs = verify_report(contracts[0], report, fixture)
        (fixture / 'reviewed-packet.json').unlink()
        try:
            build_report(fixture)
        except ValueError as error:
            if 'Missing required source: reviewed-packet.json' not in str(error):
                raise
            negative = str(error)
        else:
            raise AssertionError('negative source fixture was accepted')
    print(json.dumps({'semantic': semantic, 'case_contracts': len(contracts),
                      'positive_measurements': list(outputs),
                      'negative_rejection': negative,
                      'physical_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
