import pytest
from evals.run_eval import main
import os
from core.db import DBContext

def test_run_eval_dry_run(tmp_path):
    # Run the eval runner in dry-run mode
    # It should generate data, run phase 1, run phase 2, and evaluate.
    
    # We will pass the tmp_path as the base directory so it doesn't pollute the main project
    res = main(dry_run=True, base_dir=str(tmp_path))
    
    assert res["success"] == True
    assert "score" in res
