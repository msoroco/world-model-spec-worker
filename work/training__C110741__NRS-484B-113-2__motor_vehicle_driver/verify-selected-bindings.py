"""Revalidate selected canonical, physical, audit, fallback and compatibility receipts."""
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent.parent
sys.path[:0]=[str(ROOT/'runtime/pipeline'),str(ROOT/'runtime/pipeline/scenario_pipeline')]
from scenario_pipeline.worker_exchange.physical_preparation import validate as physical
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case
from scenario_pipeline.worker_exchange.semantic_delivery import validate as semantic
from scenario_pipeline.worker_exchange.candidate_constructions import validate as candidates
from scenario_pipeline.worker_exchange.package_compatibility import check_receipts
manifest=json.loads((HERE/'execution-manifest.json').read_text())
assignment=json.loads((ROOT/'inputs'/HERE.name/'assignment.json').read_text())
print(semantic(HERE,assignment,manifest))
for entry in manifest['cases']:
 physical(ROOT,HERE,entry)
 validate_case(HERE,entry,assignment['selection_targets'])
 print(candidates(HERE,entry,'NRS-484B-113-2','C110741',True,True,4))
check_receipts(ROOT,HERE,manifest)
print('physical, delivery, semantic, candidate and compatibility bindings passed')
