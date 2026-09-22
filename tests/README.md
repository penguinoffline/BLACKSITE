# BLACKSITE v1.0 Tests

## Please note that the automated test suite and synthetic test inputs were created with AI assistance and manually reviewed.

## Main automated core suite

`test_blacksite_v1_validation_rev4.py` is the non-GUI V&V suite.

It loads BLACKSITE core functions directly from the production source and uses the analysis logic without launching the Qt and Matplotlib GUI.

### Run

Please put the test file next to the BLACKSITE source or set `BLACKSITE_PATH`:

```bash
BLACKSITE_PATH="/full/path/to/BLACKSITE_v1.0.py" pytest -q test_blacksite_v1_validation_rev4.py
```

For more detail:

```bash
BLACKSITE_PATH="/full/path/to/BLACKSITE_v1.0.py" pytest -vv test_blacksite_v1_validation_rev4.py
```

### Results

The latest verified test results, known expected failure, optional performance result, and additional validation are documented in [docs/VALIDATION.md](../docs/VALIDATION.md).
The performance test is skipped by default because its runtime depends on the computer running the suite:

```bash
BLACKSITE_PATH="/full/path/to/BLACKSITE_v1.0.py" BLACKSITE_RUN_PERF=1 pytest -q test_blacksite_v1_validation_rev4.py
```

## Additional validation

Additional loader, stress, GUI, real data, and soak testing is documented in [docs/VALIDATION.md](../docs/VALIDATION.md).