"""Replay the six retained synthetic exception source packets and negatives."""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from exception_case import BRANCHES, inspect_case


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, packet):
    path.write_text(json.dumps(packet,sort_keys=True)+'\n')


def rejected(path, suffix, frames, expected):
    try:
        inspect_case(path,suffix,frames)
    except ValueError as error:
        assert expected in str(error), (str(error),expected)
        return str(error)
    raise AssertionError('Altered exception source passed: '+suffix)


def main():
    receipt=json.loads((HERE/'exception-absence-proof.json').read_text())
    assert receipt['passed'] and len(receipt['rows'])==6
    frames=list(range(1000,1480))
    checked=[]
    for row in receipt['rows']:
        suffix=row['case_suffix']
        branch,polarity=BRANCHES[suffix]
        path=HERE/row['positive_source_path']
        assert path.parent==HERE/'exception-polarity-sources'/suffix
        assert path.is_file() and sha(path)==row['positive_source_sha256']
        packet=json.loads(path.read_text())
        assert packet['synthetic_diagnostic'] is True
        assert packet['original_frames']==frames
        assert packet['branch']==branch and packet['requested_polarity']==polarity
        assert row['physical_observation_claimed'] is False and row['legal_verdict'] is None
        with tempfile.TemporaryDirectory() as temp:
            scratch=Path(temp)
            shutil.copytree(path.parent,scratch/'case')
            negative=scratch/'case/exception_context.json'
            if polarity=='present' and branch=='police_or_device_direction':
                encoded=scratch/'case/parking-pixels.hex'
                (scratch/'case/parking.mkv').write_bytes(bytes.fromhex(encoded.read_text().strip()))
                assert sha(scratch/'case/parking.mkv')==packet['original_pixel_sha256']
            positive=inspect_case(negative,suffix,frames)
            assert positive['physical_observation_claimed'] is False
            altered=json.loads(negative.read_text())
            if polarity=='absent':
                altered['observed_exception_source_ids']=['unexpected-source']
            elif branch=='compliance_with_law':
                altered['cited_law_text_sha256']='0'*64
            elif branch=='police_or_device_direction':
                altered['original_pixel_sha256']='0'*64
            else:
                actor=scratch/'case/other_actor_history.jsonl'
                actor.write_text(''.join(json.dumps({'native_frame':frame,
                    'conflict_occupancy':False})+'\n' for frame in frames))
            if not (polarity=='present' and branch=='necessary_traffic_conflict'):
                write(negative,altered)
            assert rejected(negative,suffix,frames,row['controlled_negative_error'])
            altered=json.loads(path.read_text())
            altered['original_frames'].pop()
            write(negative,altered)
            assert rejected(negative,suffix,frames,row['truncated_frame_negative_error'])
            if polarity=='present' and branch=='necessary_traffic_conflict':
                actor=scratch/'case/other_actor_history.jsonl'
                shutil.copy2(path.parent/'other_actor_history.jsonl',actor)
                ego=scratch/'case/ego_response_history.jsonl'
                source_rows=[json.loads(line) for line in (path.parent/'ego_response_history.jsonl').read_text().splitlines()]
                assert len(source_rows)==len(frames)
                assert [r['native_frame'] for r in source_rows]==frames
                assert [i for i,r in enumerate(source_rows) if r['brake_applied']]==packet['ego_brake_frames']
                assert source_rows[221]['speed_mps']<source_rows[220]['speed_mps']
                write(negative,packet)
                for index,mutation,expected in (
                    (221,{'brake_applied':False},'Ego brake source does not match'),
                    (221,{'speed_mps':4.0},'Ego brake has no measured deceleration'),
                    (221,{'native_frame':9999},'Ego response original frame join differs')):
                    altered_rows=json.loads(json.dumps(source_rows))
                    altered_rows[index].update(mutation)
                    ego.write_text(''.join(json.dumps(r)+'\n' for r in altered_rows))
                    assert rejected(negative,suffix,frames,expected)
                ego.unlink()
                assert rejected(negative,suffix,frames,'Missing required source: ego_response_history.jsonl')
        checked.append({'case_suffix':suffix,'branch':branch,'polarity':polarity,
                        'source_sha256':sha(path),'positive':True,
                        'controlled_negative':True,'truncated_join_negative':True,
                        'ego_response_negatives':4 if suffix=='exception_1_2' else 0})
    proof={'format':'c110454-retained-exception-source-audit-v1','passed':True,
           'synthetic_only':True,'physical_or_legal_applicability':False,'rows':checked}
    (HERE/'retained-exception-source-audit.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof,sort_keys=True))


if __name__=='__main__':
    main()
