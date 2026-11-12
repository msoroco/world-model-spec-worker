"""Independent saved-source check of the aggressive-driving window report.

This is a preparatory source audit, not the full delivery or comparison audit.
It rejects stale source bindings and a changed candidate window.
"""

from hashlib import sha256
import json
from pathlib import Path

from aggressive_window_measurement import measure


def audit(attempt, report_path):
    root = Path(attempt)
    report = json.loads(Path(report_path).read_text())
    if report.get('format') != 'worker-analysis-report':
        raise ValueError('Wrong saved analysis format')
    packet = report.get('measurements', {}).get('aggressive_window_observation')
    if not isinstance(packet, dict):
        raise ValueError('Missing aggressive window measurement')
    sources = packet.get('sources')
    if not isinstance(sources, dict) or not sources:
        raise ValueError('Missing measurement source bindings')
    for name, expected in sources.items():
        source = (root / name).resolve()
        if not source.is_relative_to(root.resolve()) or not source.is_file():
            raise ValueError('Missing retained measurement source: ' + name)
        if sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError('Changed retained measurement source: ' + name)
    current = measure(root / 'driving_trace.jsonl',
                      root / 'event_annotations.json', root)
    if packet.get('value') != current:
        raise ValueError('Candidate window differs from retained sources')
    if (report.get('physical_acceptance_claimed') is not False or
            report.get('legal_acceptance_claimed') is not False or
            current['aggressive_driving_legal_judgment'] is not None):
        raise ValueError('Unsupported acceptance or legal judgment')
    return {'format': 'worker-aggressive-source-audit',
            'case_id': report['case_id'], 'sources_checked': len(sources),
            'candidate_window': current['candidate_window'],
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}
