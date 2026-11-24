"""Retain compact active public and saved receipts for 20 draft candidates."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE / 'cases/branch-requests'
DEST = BASE / 'current-proof-grid'
GRID = ('signal_red_stop', 'signal_red_proceed', 'signal_green_stop', 'signal_green_proceed',
        'officer_no_direction_stop', 'officer_no_direction_proceed',
        'officer_directed_stop', 'officer_directed_proceed')
PLACEMENT = ('placement_record_absent', 'placement_record_supplied')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy(source, target):
    if not source.is_file():
        raise ValueError('Missing active-runtime proof: ' + str(source))
    data = source.read_bytes()
    if len(data) > 2 * 1024 * 1024 or data.endswith(b'\n\n') or any(
            line.endswith((b' ', b'\t')) for line in data.splitlines()):
        raise ValueError('Returned proof is too large or has whitespace: ' + str(source))
    target.write_bytes(data)
    return sha(target)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    entries = []
    for group, suffixes, scratch_name, version, manifest_name in (
            ('joint_grid', GRID, 'c10389-branch-compat-repo', 'v3', 'branch-draft-manifest.json'),
            ('placement', PLACEMENT, 'c10389-placement-compat-repo', 'v5', 'placement-draft-manifest.json')):
        manifest_sha = sha(HERE / manifest_name)
        scratch = ROOT / '.runtime-work' / scratch_name / '.runtime-work'
        for suffix in suffixes:
            for candidate in ('primary', 'fallback1'):
                stem = suffix + '-' + candidate
                compat = scratch / ('compat-' + version) / stem
                saved = scratch / ('saved-' + version) / stem / 'v0001'
                target = DEST / stem
                target.mkdir(exist_ok=True)
                checks = {}
                for name, source in (
                        ('candidate-selection.json', compat / 'candidate-selection.json'),
                        ('compatibility.json', compat / 'compatibility.json'),
                        ('analysis.log', compat / 'compatibility-analysis.log'),
                        ('negative-analysis.log', compat / 'negative-analysis.log'),
                        ('processing.json', saved / 'processing.json'),
                        ('saved-analysis.log', saved / 'analysis.log')):
                    checks[name] = copy(source, target / name)
                selection = json.loads((target / 'candidate-selection.json').read_text())
                receipt = json.loads((target / 'compatibility.json').read_text())
                processing = json.loads((target / 'processing.json').read_text())
                construction = BASE / (suffix if candidate == 'primary' else stem) / 'construction.json'
                construction_sha = sha(construction)
                if (selection.get('manifest_sha256') != manifest_sha or
                        selection.get('construction_sha256') != construction_sha or
                        receipt.get('construction_sha256') != construction_sha or
                        receipt.get('passed') is not True or
                        receipt.get('runtime_manifest_sha256') != sha(ROOT / 'runtime/SOURCE-MANIFEST.json') or
                        processing.get('passed') is not True or processing.get('recorded_only') is not True):
                    raise ValueError('Draft active runtime proof differs: ' + stem)
                summary = {'case_id': HERE.name + '__' + suffix, 'candidate_id': candidate,
                           'group': group, 'draft_manifest_sha256': manifest_sha,
                           'construction_sha256': construction_sha, 'file_sha256': checks,
                           'runtime_manifest_sha256': receipt['runtime_manifest_sha256'],
                           'diagnostic_only': True, 'selected_delivery': False}
                path = target / 'summary.json'
                path.write_text(json.dumps(summary, indent=2) + '\n')
                entries.append({'stem': stem, 'summary_sha256': sha(path)})
    index = {'format': 'c10389-joint-grid-and-placement-current-proof-v1',
             'candidate_count': len(entries), 'entries': entries,
             'selected_delivery': False}
    path = DEST / 'index.json'
    path.write_text(json.dumps(index, indent=2) + '\n')
    return index


if __name__ == '__main__':
    print(json.dumps({'candidate_count': main()['candidate_count']}))
