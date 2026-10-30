import importlib.util,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('b',ROOT/'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver/package_builder.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
ids=json.loads((ROOT/'partitions/demo-test-02.json').read_text())['assignment_ids'];ids += [r['assignment_id'] for r in json.loads((ROOT/'work'/ids[0]/'additional-bindings.json').read_text())]
for i,aid in enumerate(ids):
 if i%int(sys.argv[2])!=int(sys.argv[1]):continue
 print('PROVING',aid,flush=True);b.prove(ROOT/'work'/aid,ROOT/'runtime/main-pipeline-v1/library',ROOT/'.runtime-work/decoder/.lake/build/bin/adapterCheck');print('PASSED',aid,flush=True)
