# Contributing

BioMAP is a research repository. Changes should remain reproducible, reviewable, and explicit about their scientific assumptions.

## Before making changes

1. Create a focused branch from the current default branch.
2. Install `requirements-dev.txt` and the locked frontend dependencies.
3. Configure local paths through `.env`; never hardcode machine-specific paths.
4. Check the relevant source coverage before changing indicator or forecast semantics.

## Code guidelines

- Prefer small functions with descriptive names over inline procedural blocks.
- Keep data units and conversion rules visible in code and metadata.
- Distinguish observed values, predictions, proxies, and placeholders.
- Add a regression test when fixing a calculation or data-mapping bug.
- Avoid debug-only scripts when the same behavior can be expressed as a test.
- Do not commit generated outputs, datasets, checkpoints, caches, or virtual environments.

## Validation

Run the checks relevant to your change:

```bash
ruff check backend_api scripts test_*.py
python -m compileall -q backend_api scripts
pytest
```

```bash
cd web-ui
npm run check
```

Model-dependent checks must run in the BioAnalyst environment with the documented checkpoint and input mode. Include those details in the pull request.

## Pull requests

Explain:

- what changed and why;
- which workflow is affected;
- any change to units, data sources, assumptions, or output schemas;
- the commands used for validation;
- known limitations or follow-up work.

Keep unrelated local work out of the commit.
