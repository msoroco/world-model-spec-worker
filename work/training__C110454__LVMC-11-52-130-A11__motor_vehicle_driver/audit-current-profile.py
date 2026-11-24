"""Independent checkpoint audit of current-profile source and saved processing."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCRATCH=ROOT/'.runtime-work/c110454-current-profile'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def audit():
    manifest=HERE/'draft-current-primary-manifest.json';m=json.loads(manifest.read_text())
    assert len(m['cases'])==2
    hashes={}
    for entry in m['cases']:
        path=HERE/entry['construction'];assert sha(path)==entry['construction_sha256']
        cfg=json.loads(next(f['content'] for f in json.loads(path.read_text())['files'] if f['path']=='config.json'))
        assert cfg['duration_s']==30 and cfg['rate_hz']==20
        assert [x['name'] for x in cfg['cameras']]==['overview','approach','reference_corner','driver_reference']
        hashes[entry['case_id']]=entry['construction_sha256']
    probe=json.loads((HERE/'current-process-saved-probe.json').read_text())
    assert probe['original_sources_preserved'] and probe['synthetic_diagnostic'] and not probe['native_executed']
    version=SCRATCH/'processed-v4-witness_1/v0001'
    stage=version/'analysis';converted=version/'converted'
    assert all((stage/(x+'.mkv')).is_file() for x in ('overview','approach','reference_corner','driver_reference'))
    assert (stage/'raw.mkv').is_file()
    assert (stage/'channels/drv.standing_or_parked.jsonl').is_file()
    report=json.loads((converted/'adapter_report.json').read_text())
    assert report['frames']==600 and report['required_measurements_complete'] is True
    assert probe['exit_code']!=0 and probe['feedback']['error']=='TrafficSpec decoder rejected output: manifest is not complete'
    assert probe['feedback']['native_replay_requested'] is False
    return {'format':'c110454-current-profile-checkpoint-v1','manifest_sha256':sha(manifest),
            'case_sha256':hashes,'pinned_offline_passed':2,
            'four_current_profile_source_cameras':True,'saved_raw_four_view_composed':True,
            'saved_channels_rebuilt_from_originals':True,'adapter_converted_frames':600,
            'adapter_required_observations_complete':True,
            'lean_decoder_passed':False,'lean_decoder_error':probe['feedback']['error'],
            'originals_preserved':True,'native_executed':False,'delivery_ready':False}
if __name__=='__main__':print(json.dumps(audit(),indent=2,sort_keys=True))
