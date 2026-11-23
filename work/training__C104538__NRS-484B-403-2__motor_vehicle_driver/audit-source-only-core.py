"""Audit both unselected source-only saved/Core diagnostics independently."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit():
    outcomes=[]
    for suffix in ('witness_1','witness_2'):
      for candidate in ('primary','fallback1','fallback2','fallback3'):
        log=HERE/f'source-only-core-{suffix}-{candidate}.log'
        receipt=json.loads(log.read_text())
        attempt=Path(receipt['scratch'])/'attempt'
        report=json.loads((attempt/'analysis-report.json').read_text())
        result=json.loads((attempt/'result.json').read_text())
        derived=report['derived_recording_evidence']
        if (receipt['case']!=suffix or receipt['candidate']!=candidate
            or receipt['render_frames']!=600 or not receipt['final_decode_passed']
            or not receipt['core']['decoder_checked']
            or not receipt['missing_retained_evidence_rejected']):
            raise ValueError('Saved/Core proof incomplete')
        if result['accepted'] or result['setup_confirmed'] or result['legal_verdict_claimed']:
            raise ValueError('Synthetic diagnostic claims acceptance')
        if report['measurements']['signed_u_turn']['value']['u_turn_within_governed_region_observed']!=(suffix=='witness_2'):
            raise ValueError('Controlled witness outcome differs')
        if len(derived['channels'])!=8 or derived['channels']!=receipt['source_derived_channels']:
            raise ValueError('Derived channel inventory differs')
        for name,digest in derived['channels'].items():
            path=attempt/'channels'/(name+'.jsonl')
            channel=rows(path)
            if len(channel)!=600 or sha(path)!=digest:
                raise ValueError('Derived channel source or frame count differs')
            if any(row['native_frame']!=index+100 or row['source_sha256']!=derived['source_hashes']
                   for index,row in enumerate(channel)):
                raise ValueError('Derived channel frame/source binding differs')
        if sha(attempt/'context.json')!=derived['context_sha256']:
            raise ValueError('Derived context digest differs')
        for name,digest in derived['source_hashes'].items():
            if sha(attempt/name)!=digest:
                raise ValueError('Retained source digest differs')
        outcomes.append({'case':suffix,'candidate':candidate,'log_sha256':sha(log),
                         'analysis_sha256':sha(attempt/'analysis-report.json'),
                         'channel_count':8,'frames_per_channel':600})
    if len(outcomes)!=8:
        raise ValueError('Source-only candidate inventory incomplete')
    return {'format':'c104538-source-only-current-core-audit-v1','passed':True,
            'cases':outcomes,'selected':False,'native_executed':False,
            'original_pixels_reviewed':False,'accepted':False}


if __name__=='__main__':
    value=audit()
    (HERE/'source-only-core-audit.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'passed':True,'cases':len(value['cases'])}))
