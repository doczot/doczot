# Golden Files

Golden files contain expected DocZot output for known fixtures. They serve as regression tests: if the output changes unexpectedly, the test fails.

## Files

- `simple_test_app.json` - Expected SystemGraph for `doczot_analyzer/tests/fixtures/simple_test_app/`

## Updating Golden Files

After an intentional change to scanner or analyzer behavior:

```bash
doczot validate golden-update
```

Or regenerate manually:

```python
from validation.golden.generate import regenerate_golden_files
regenerate_golden_files()
```

Always review the diff before committing updated golden files.
