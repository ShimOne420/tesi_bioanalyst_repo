# Code Cleanup Report — 23 July 2026

## Scope

This cleanup focused on the default `main` worktree. It preserved the existing research workflows and the untracked architecture and rollout documentation already present in the workspace.

## Changes

### Removed obsolete material

- Removed `SUMMARY_OF_FIXES.md`, a temporary troubleshooting note containing stale machine-specific paths and instructions already superseded by the code and project documentation.
- Replaced the dataset-dependent `test_ndvi_fix.py` debug script with deterministic unit tests based on synthetic column names.
- Removed unused imports, unnecessary f-strings, and a dead alignment-diagnostic assignment.

### Improved reproducibility

- Added `requirements-dev.txt` with pinned Ruff and pytest versions.
- Added `pyproject.toml` with shared pytest discovery and Ruff rules.
- Replaced the unsupported frontend `next lint` script with explicit `typecheck` and `check` commands.
- Documented `npm ci`, environment templates, local data boundaries, and validation commands.

### Improved documentation

- Rewrote the root README in English.
- Described the observed and forecast workflows, architecture, directory layout, setup, configuration, data rules, commands, validation, API, dashboard, limitations, and research-use constraints.
- Rewrote the contribution guide in English with clear scientific and engineering expectations.
- Replaced absolute local links with repository-relative links.

### Preserved user work

- Kept the pre-existing rollout report and `docs/architecture_study/` files.
- Did not modify or merge the separate `main-stable-observed-backup` worktree, which contains unrelated local changes.

## Validation

Completed successfully:

- `ruff check backend_api scripts test_*.py`
- `python -m compileall -q backend_api scripts test_*.py`
- `git diff --check`

Not completed in the current desktop environment:

- `pytest` could not collect the suite with the system interpreter because the scientific dependencies are not installed there. The existing BioAnalyst virtual environments contain the scientific stack but do not contain pytest.
- The Next.js type-check and production-build processes started without reporting compilation errors but did not terminate in the available desktop session, so they are not recorded as passing.

The reproducible commands and missing development dependencies are now documented in `requirements-dev.txt`. Model-dependent tests still require the configured BioAnalyst/PyTorch environment and local data assets.
