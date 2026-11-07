"""Independent CPU contract for five draft Native runner frame-map writers."""
import ast
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.native_output import frame_record
NAMES=(
 'training__C329610__NRS-484B-400-2a__motor_vehicle_driver',
 'training__C329610__NRS-484B-400-2b__motor_vehicle_driver',
 'training__C382355__NRS-484B-400-1__motor_vehicle_driver',
 'training__C382355__NRS-484B-223-4a__motor_vehicle_driver',
 'training__C382389__NRS-484B-223-4b__motor_vehicle_driver')


def main():
    records=[]
    for name in NAMES:
        runner=ROOT/'work'/name/'native/runner.py'
        source=runner.read_text()
        assert 'frame_file.write(json.dumps(frame_map_row(index,frame,time_s))' in source
        function=next(node for node in ast.parse(source).body
                      if isinstance(node,ast.FunctionDef) and node.name=='frame_map_row')
        scope={'math':math}
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(runner),'exec'),scope)
        frame_map_row=scope['frame_map_row']
        row=frame_map_row(0,100,.05)
        assert row==frame_record(0,100,.05)
        for bad in ((-1,100,.05),(0,-1,.05),(0,100,float('nan')),(0,100,True)):
            try:frame_map_row(*bad)
            except ValueError:pass
            else:raise AssertionError('Invalid frame map accepted')
        records.append({'assignment_id':name,'runner_sha256':hashlib.sha256(runner.read_bytes()).hexdigest(),
                        'frame_map':row,'positive_and_four_negative_checks_passed':True})
    print(json.dumps({'passed':True,'assignments':records,'native_executed':False},indent=2))


if __name__=='__main__':main()
