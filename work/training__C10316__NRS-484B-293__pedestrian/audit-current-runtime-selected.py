"""Independently check current-runtime pedestrian sources and candidate pairs."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SPEC = importlib.util.spec_from_file_location('c10316_raw_audit_current', HERE/'audit-update015-saved-evidence.py')
SOURCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCE)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def attempt(suffix, candidate):
    matches=[p for p in (ROOT/'.runtime-work').glob(f'c10316-current-{suffix}-{candidate}-*-compat')
             if (p/'compatibility.json').is_file()]
    require(len(matches)==1, 'Exactly one current diagnostic attempt required: '+suffix+' '+candidate)
    return matches[0]


def main():
    manifest=read(HERE/'current-runtime-reproof-manifest.json')
    progress=read(HERE/'current-runtime-matrix-progress.json')
    require(progress['completed']==8 and len(progress['rows'])==8,
            'All eight candidate proofs required')
    entries={e['case_id'].rsplit('__',1)[-1]:e for e in manifest['cases']}
    require(set(entries)=={'reference','contrast'}, 'Selected pedestrian pair differs')
    audited=[]
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        pair=[]
        for suffix in ('reference','contrast'):
            entry=entries[suffix]
            chosen=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            folder=attempt(suffix,candidate)
            proof=HERE/'current-runtime-selected-proof'/suffix/candidate
            receipt=read(proof/'compatibility.json')
            processing=read(proof/'saved-processing.json')
            require(receipt['passed'] and receipt['runtime_manifest_sha256']==manifest['runtime_manifest_sha256'] and
                    receipt['construction_sha256']==chosen['construction_sha256'] and
                    receipt['negative_log_sha256']==sha(proof/'negative-analysis.log') and
                    'Missing required source: native_samples.jsonl' in (proof/'negative-analysis.log').read_text() and
                    processing['passed'] and processing['recorded_only'] and processing['originals_preserved'] and
                    not processing['missing_evidence'] and not processing['physical_acceptance_claimed'] and
                    not processing['legal_acceptance_claimed'] and
                    processing['native_revision']['construction_sha256']==chosen['construction_sha256'],
                    'Current-runtime receipt binding differs: '+suffix+' '+candidate)
            source=SOURCE.audit_attempt(folder)
            require(source['case_id']==entry['case_id'] and source['candidate_id']==candidate,
                    'Independent source identity differs')
            for name,digest in source['source_sha256'].items():
                require(processing['original_source_hashes'].get(name)==digest,
                        'Saved processing changed original source: '+name)
            for name in ('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'):
                require(processing['original_source_hashes'].get(name)==sha(folder/name),
                        'Saved processing changed source camera: '+name)
            audited.append({'case_id':entry['case_id'],'candidate_id':candidate,
                            'construction_sha256':chosen['construction_sha256'],
                            'compatibility_sha256':sha(proof/'compatibility.json'),
                            'saved_sha256':sha(proof/'saved-processing.json'),
                            'original_source_sha256':source['source_sha256']})
            pair.append(folder)
        ref,con=pair
        require((ref/'crosswalk-context.json').read_bytes()==(con/'crosswalk-context.json').read_bytes(),
                'Controlled pair changed crosswalk context')
        a,b=(read(p/'config.json') for p in pair)
        for key in ('cell_id','law_id','actor','duration_s','rate_hz','required_atoms',
                    'source_packets','cameras','recording_description','candidate_id'):
            require(a[key]==b[key], 'Controlled pair changed fixed setting: '+key)
        left=SOURCE.lines(ref/'native_samples.jsonl')
        right=SOURCE.lines(con/'native_samples.jsonl')
        require(len(left)==len(right)==240, 'Controlled pair lacks full source window')
        for x,y in zip(left,right):
            require(x['native_frame']==y['native_frame'] and abs(x['time_s']-y['time_s'])<1e-9 and
                    abs(x['pedestrian_xy_m'][0]-y['pedestrian_xy_m'][0])<1e-9 and
                    abs(y['pedestrian_xy_m'][1]-x['pedestrian_xy_m'][1]-1.3)<1e-9 and
                    x['pedestrian_forward_xy']==y['pedestrian_forward_xy'],
                    'Controlled pair changed more than lateral path')
    first=attempt('reference','primary')
    changed={name:SOURCE.lines(first/name) for name in SOURCE.SOURCES}
    changed['native_samples.jsonl'][8]['native_frame']=999
    try:
        SOURCE.audit_attempt(first,changed)
    except ValueError:
        pass
    else:
        raise ValueError('Changed Native frame was accepted')
    report={'format':'c10316-current-runtime-independent-source-audit-v1',
            'runtime_manifest_sha256':manifest['runtime_manifest_sha256'],
            'passed':True,'attempts':audited,'controlled_pairs':4,
            'negative_changed_frame_rejected':True,
            'original_native_proven':False,'physical_or_legal_acceptance':False}
    path=HERE/'current-runtime-selected-source-audit.json'
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'attempts':len(audited),'controlled_pairs':4,
                      'changed_frame_rejected':True}))


if __name__=='__main__':
    main()
