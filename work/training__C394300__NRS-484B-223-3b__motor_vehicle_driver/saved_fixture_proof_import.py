"""Share only the deterministic synthetic source generator with the independent audit."""
from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
_path=Path(__file__).with_name('saved-fixture-proof.py')
_spec=spec_from_file_location('c394300_saved_fixture',_path)
_module=module_from_spec(_spec);_spec.loader.exec_module(_module)
make_base=_module.make_base
