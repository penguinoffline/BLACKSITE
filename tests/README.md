# BLACKSITE v1.0 Tests

## Note

The automated test suite and synthetic test inputs were created with AI assistance and manually reviewed.

## Main automated core suite

`test_blacksite_v1_validation_rev4.py` is the non-GUI V&V suite.

It loads BLACKSITE core functions directly from the production source and uses the analysis logic without launching the Qt and Matplotlib GUI.

### If you want to run the test suite yourself

From the repository root:

```bash
BLACKSITE_PATH="$PWD/BLACKSITE_v1.0.py" pytest -q tests/test_blacksite_v1_validation_rev4.py
```

For more detail:

```bash
BLACKSITE_PATH="$PWD/BLACKSITE_v1.0.py" pytest -vv tests/test_blacksite_v1_validation_rev4.py
```

On Windows PowerShell:

```powershell
$env:BLACKSITE_PATH = "$PWD\BLACKSITE_v1.0.py"
python -m pytest -q tests\test_blacksite_v1_validation_rev4.py
```

### Results

The latest verified test results, known expected failure, optional performance result, and additional validation are documented in [docs/VALIDATION.md](../docs/VALIDATION.md).
The performance test is skipped by default because its runtime depends on the computer running the suite:

```bash
BLACKSITE_PATH="$PWD/BLACKSITE_v1.0.py" BLACKSITE_RUN_PERF=1 pytest -q tests/test_blacksite_v1_validation_rev4.py
```

## Additional validation

Additional loader, stress, GUI, real data, and soak testing is documented in [docs/VALIDATION.md](../docs/VALIDATION.md).
