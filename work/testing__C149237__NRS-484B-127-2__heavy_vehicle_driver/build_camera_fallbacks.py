"""Build three source-camera risk fallbacks for each exact truck case.

All linked cases receive the same camera alternatives. This does not establish
real pixel coverage, truck width, Native motion or legal acceptance.
"""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
VARIANTS = (
    ('fallback1', "'overview': static(450, -1.9, 90, 0, -75)",
     "'overview': static(400, -1.9, 110, 0, -75)",
     'overview.mkv', 'both truck bodies visible across original frames',
     'source-pixel review finds a truck body outside overview framing',
     ['overview camera x 450->400 m', 'overview camera height 90->110 m']),
    ('fallback2', "'reference_corner': static(300, -24, 30, 90, -25)",
     "'reference_corner': static(330, -34, 35, 90, -25)",
     'reference_corner.mkv', 'truck body reference edge completeness',
     'source-pixel review finds a width/body reference clipped',
     ['reference corner x 300->330 m', 'reference corner y -24->-34 m',
      'reference corner height 30->35 m']),
    ('fallback3', "'approach': static(60, -1.9, 8, 0, -18)",
     "'approach': static(80, -1.9, 12, 0, -18)",
     'approach.mkv', 'lead and ego approach interval coverage',
     'source-pixel review finds the approach relation outside the frame',
     ['approach camera x 60->80 m', 'approach camera height 8->12 m']),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = (FOLDER/'runner.py').read_text()
    plans = {}
    for ident, old, new, metric_source, metric, failure, knobs in VARIANTS:
        if source.count(old) != 1:
            raise ValueError('Camera source replacement is not unique: '+ident)
        variant = FOLDER/('camera-'+ident+'-runner.py')
        variant.write_text(source.replace(old, new))
        plans[ident] = (variant, metric_source, metric, failure, knobs)
    manifest_path = FOLDER/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    directory = FOLDER/'candidate-constructions'
    directory.mkdir(exist_ok=True)
    for entry in manifest['cases']:
        primary = json.loads((FOLDER/entry['construction']).read_text())
        suffix = entry['case_id'].split('__')[-1]
        candidates = []
        for ident, (variant, metric_source, metric, failure, knobs) in plans.items():
            construction = json.loads(json.dumps(primary))
            construction['files'] = [dict(item, content=variant.read_text(),
                                          source=str(variant.relative_to(ROOT)))
                                     if item['path'] == 'runner.py' else item
                                     for item in construction['files']]
            construction['candidate_id'] = ident
            construction['mechanisms'] = primary['mechanisms'] + ['alternative source-camera placement '+ident]
            relative = 'candidate-constructions/'+suffix+'-'+ident+'.json'
            path = FOLDER/relative
            path.write_text(json.dumps(construction, indent=2)+'\n')
            candidates.append({'id': ident, 'construction': relative,
                               'construction_sha256': sha(path),
                               'trigger': {'source': metric_source, 'metric': metric,
                                           'failure_condition': failure},
                               'changed_knobs': knobs})
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'source-camera coverage of the truck body and relation may fail under Native motion; distinct camera poses are predeclared alternatives'}
        entry['candidates'] = candidates
    manifest['status'] = 'partial_eight_primaries_and_unproved_fallbacks'
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
