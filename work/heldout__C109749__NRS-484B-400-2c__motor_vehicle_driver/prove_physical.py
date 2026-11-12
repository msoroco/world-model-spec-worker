"""Exercise all saved motion outcomes with deterministic original-shaped CPU packets."""
import json
import sys
import tempfile
from pathlib import Path

from opposing_turn_physical_audit import assess, LIFECYCLE, validate_lifecycle


def row(frame, x, y, inside, actor):
    return {'frame': frame, 'time_s': frame*.05, 'center_xy': [x,y],
            'heading_xy': [1,0], 'ground_corners_xy': [[x-.2,y-.2],[x+.2,y-.2],
            [x+.2,y+.2],[x-.2,y+.2]], 'in_intersection': inside,
            'turning_left': inside, 'native_actor_id': actor}


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))


def main(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        a = [row(1,-2,0,False,1),row(2,0,0,True,1),row(3,1,0,True,1),row(4,3,0,False,1)]
        b = [row(1,2,1,False,2),row(2,1,1,True,2),row(3,0,1,True,2),row(4,-2,1,False,2)]
        paths = [root/n for n in ('subject_original.jsonl','opposing_original.jsonl',
                                  'topology_original.json','devices_original.json')]
        paths[2].write_text(json.dumps({'both_highways_two_directional':True,
                                        'same_intersection':True,'opposing_approaches':True}))
        paths[3].write_text('{"governing_device":"none"}')
        write_rows(paths[0],a);write_rows(paths[1],b)
        complete = assess(*paths,source_kind='native')
        assert complete['physical_checks']['maneuver']['status']=='met'
        b[-1]['in_intersection']=True
        write_rows(paths[1],b)
        incomplete = assess(*paths,source_kind='native')
        assert incomplete['physical_checks']['maneuver']['status']=='not_met'
        paths[1].unlink()
        missing = assess(*paths,source_kind='native')
        assert missing['physical_checks']['maneuver']['status']=='unverified'
        for name,result in [('complete_motion',complete),('incomplete_motion',incomplete),
                            ('missing_evidence',missing)]:
            result['fixture_kind']='simulated_native_cpu_packet'
            (output/f'{name}.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Physical outcome fixtures passed: met, not_met, unverified')
    assert validate_lifecycle(LIFECYCLE)
    try:
        validate_lifecycle(LIFECYCLE[:-2] + tuple(reversed(LIFECYCLE[-2:])))
    except ValueError:
        pass
    else:
        raise AssertionError('Early saved processing was not rejected')
    print('Lifecycle order and early-processing rejection passed')


if __name__=='__main__':
    main(sys.argv[1])
