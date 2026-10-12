"""Build exp-07's contract: exp-06's derivation, into `fig-checklist-exp07`.

The contract is derived exactly as exp-06's (`experiments/exp-06-full-checklist/
build_contract.py`, which documents it and verifies it) from the production
contracts and the live gold -- now with `individual-data-points`'
`is_a_plot_with_axes`. Only the target differs; the merged gold is the same
file, `examples/<ex>/checks/do-fig-checklist-cm/expected_output.json`, and is
tagged `gold-v6`.

    python experiments/exp-07-models/build_contract.py           # contract
    python experiments/exp-07-models/build_contract.py --gold    # and gold
    python experiments/exp-07-models/build_contract.py --check   # drift only
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "exp06_build_contract", HERE.parent / "exp-06-full-checklist" / "build_contract.py")
exp06 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exp06)

exp06.TARGET = exp06.CHECKLISTS / "fig-checklist-exp07"

if __name__ == "__main__":
    raise SystemExit(exp06.main(sys.argv[1:]))
