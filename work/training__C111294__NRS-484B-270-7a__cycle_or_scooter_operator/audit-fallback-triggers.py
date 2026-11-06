"""CPU proof that three distinct fallback triggers bind to their source bytes."""
import importlib.util
import json
from pathlib import Path
import tempfile

NATIVE=Path(__file__).resolve().parent/'native'
spec=importlib.util.spec_from_file_location('engineering',NATIVE/'engineering.py')
engineering=importlib.util.module_from_spec(spec);spec.loader.exec_module(engineering)

def main():
    metrics={'source_kind':'original_native_and_video',
             'max_bicycle_route_cross_track_error_m':.5,
             'min_motorist_conflict_clearance_s':.5,
             'min_projected_body_frame_margin_px':30}
    assert len({engineering.TRIGGERS[k]['metric'] for k in engineering.TRIGGERS})==3
    assert len({json.dumps(engineering.parameters('witness_1',key)['knobs'],sort_keys=True)
                for key in engineering.CANDIDATES})==4
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/'observed-metrics.json'
        path.write_text(json.dumps(metrics,sort_keys=True)+'\n')
        digest=__import__('hashlib').sha256(path.read_bytes()).hexdigest()
        for candidate in ('fallback1','fallback2','fallback3'):
            assert engineering.evaluate_trigger(candidate,metrics,path,digest)
            altered=dict(metrics)
            altered[engineering.TRIGGERS[candidate]['metric']]=(
                0 if engineering.TRIGGERS[candidate]['op']=='>' else 100)
            altered['source_kind']='original_native_and_video'
            path.write_text(json.dumps(altered,sort_keys=True)+'\n')
            changed=__import__('hashlib').sha256(path.read_bytes()).hexdigest()
            assert not engineering.evaluate_trigger(candidate,altered,path,changed)
            try:engineering.evaluate_trigger(candidate,altered,path,digest)
            except ValueError as error:assert 'hash differs' in str(error)
            else:raise AssertionError('Changed source accepted')
            path.write_text(json.dumps(metrics,sort_keys=True)+'\n')
        synthetic=dict(metrics);synthetic['source_kind']='synthetic_cpu'
        path.write_text(json.dumps(synthetic,sort_keys=True)+'\n')
        changed=__import__('hashlib').sha256(path.read_bytes()).hexdigest()
        try:engineering.evaluate_trigger('fallback1',synthetic,path,changed)
        except ValueError as error:assert 'not bound' in str(error)
        else:raise AssertionError('Synthetic metric activated physical fallback')
    print(json.dumps({'passed':True,'three_distinct_fallback_metrics':True,
                      'positive_negative_and_hash_rejection_per_fallback':True,
                      'physical_trigger_observation_claimed':False},sort_keys=True))

if __name__=='__main__':main()
