"""Independent CPU audit of authored right-pass clearance requests."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
NATIVE = ROOT/'native'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def validate_pair(ref_cfg, ref, con_cfg, con):
    require({k: v for k, v in ref_cfg.items() if k not in
             ('case_id', 'tracks_sha256', 'requested_lateral_apex_y_m',
              'requested_nominal_body_gap_m')} ==
            {k: v for k, v in con_cfg.items() if k not in
             ('case_id', 'tracks_sha256', 'requested_lateral_apex_y_m',
              'requested_nominal_body_gap_m')},
            'Pair changes a fixed config condition')
    for a, b in zip(ref, con):
        require(all(a[key] == b[key] for key in
                    ('time_s', 'ego_x_m', 'lead_x_m', 'lead_y_m',
                     'ego_requested_speed_mps', 'lead_requested_speed_mps')),
                'Pair changes more than lateral clearance')
    require(ref_cfg['requested_nominal_body_gap_m'] >
            con_cfg['requested_nominal_body_gap_m'] > 0,
            'Reference/contrast body gap is not a sweep')


def audit():
    road = NATIVE/'right-pass-road.xodr'
    tree = ET.parse(road)
    lanes = tree.findall('.//laneSection/right/lane')
    require([(x.attrib['id'], x.attrib['type']) for x in lanes] ==
            [('-1', 'driving'), ('-2', 'driving')],
            'Expected two authored one-way driving lanes')
    require(all(float(x.find('width').attrib['a']) == 3.5 for x in lanes),
            'Right-pass corridor width differs')
    manifest = json.loads((NATIVE/'manifest.json').read_text())
    require(manifest['assignment_id'] == ROOT.name and
            manifest['road_sha256'] == sha(road) and
            manifest['assignment_sha256'] == sha(REPO/'inputs'/ROOT.name/'assignment.json') and
            manifest['case_plan_sha256'] == sha(ROOT/'case-plan.json') and
            len(manifest['entries']) == 8 and
            manifest['original_native_observed'] is False,
            'Source-bound request manifest differs')
    lookup = {}
    for entry in manifest['entries']:
        witness = entry['case_id'].split('__')[-1]
        candidate = entry['candidate_id']
        require(witness in ('reference', 'contrast') and
                candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'),
                'Unexpected case or fallback')
        folder = NATIVE/'drafts'/witness/candidate
        cfg = json.loads((folder/'config.json').read_text())
        track = rows(folder/'requested-tracks.jsonl')
        require(entry['config_sha256'] == sha(folder/'config.json') and
                entry['tracks_sha256'] == sha(folder/'requested-tracks.jsonl') and
                cfg['road_sha256'] == sha(road) and
                cfg['tracks_sha256'] == entry['tracks_sha256'] and
                cfg['assignment_sha256'] == manifest['assignment_sha256'] and
                cfg['case_plan_sha256'] == manifest['case_plan_sha256'] and
                cfg['law_id'] == 'NRS-484B-210-2' and
                cfg['cell_id'] == 'C146314' and
                cfg['original_native_observed'] is False and
                cfg['legal_safety_verdict'] is None and len(track) == 240,
                'Candidate source identity or duration differs')
        for i, row in enumerate(track):
            require(row['frame'] == i and row['time_s'] == (i+1)/20 and
                    row['source_kind'] == 'authored_native_request' and
                    row['case_id'] == cfg['case_id'] and
                    row['candidate_id'] == candidate and
                    row['road_id'] == 210 and
                    row['lead_y_m'] == -1.75 and
                    row['lead_lane_id'] == -1 and
                    row['ego_lane_id'] in (-1, -2) and
                    row['actual_pass_observed'] is False and
                    row['actual_clearance_observed'] is False and
                    row['legal_safety_verdict'] is None and
                    all(math.isfinite(row[key]) for key in
                        ('ego_x_m', 'ego_y_m', 'lead_x_m', 'lead_y_m')),
                    'Requested row identity or provenance differs')
        require(any(r['ego_lane_id'] == -2 for r in track) and
                any(r['ego_x_m'] > r['lead_x_m'] and
                    r['ego_y_m'] < r['lead_y_m'] for r in track),
                'Right-side overtake request never passes lead')
        lookup[witness, candidate] = (cfg, track)
    require(len(lookup) == 8, 'Duplicate or missing candidate')
    gaps = {}
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        ref_cfg, ref = lookup['reference', candidate]
        con_cfg, con = lookup['contrast', candidate]
        validate_pair(ref_cfg, ref, con_cfg, con)
        gaps[candidate] = [ref_cfg['requested_nominal_body_gap_m'],
                           con_cfg['requested_nominal_body_gap_m']]
    return {'format': 'c146314-210-2-request-audit-v1',
            'candidates': len(lookup), 'nominal_gap_pairs_m': gaps,
            'original_native_observed': False, 'legal_safety_verdict': None}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
