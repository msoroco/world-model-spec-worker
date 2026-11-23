"""Saved-only original-source measurement, before canonical conversion.

This command reads sealed site and Native frame sources. It does not execute
CARLA, alter a captured source, issue a legal verdict, or claim acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_crossing import measure, source


def build(site_ref, events_ref, attempt_root):
    site_path = source(site_ref, attempt_root)
    site = json.loads(site_path.read_text())
    facts = measure(site, attempt_root, events_ref)
    return {
        'format': 'worker-pedestrian-crossing-measurement',
        'assignment_id': 'testing__C111125__NRS-484B-307-2b__pedestrian',
        'site_source': site_ref,
        'events_source': events_ref,
        'site_source_sha256': hashlib.sha256(site_path.read_bytes()).hexdigest(),
        'facts': facts,
        'legal_verdict': None,
        'physical_acceptance': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt-root', required=True)
    parser.add_argument('--site-ref', required=True)
    parser.add_argument('--events-ref', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    site_ref = json.loads(Path(args.site_ref).read_text())
    events_ref = json.loads(Path(args.events_ref).read_text())
    result = build(site_ref, events_ref, args.attempt_root)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + '.tmp')
    tmp.write_text(json.dumps(result, indent=2) + '\n')
    tmp.replace(output)


if __name__ == '__main__':
    main()
