# 01 — Packaging approach for `src/mrv`

**Status**: Approved in principle — Option B. Implementation (creating
`pyproject.toml`, running `pip install -e .`) has not started; this note
now also pins the exact outline and `conftest.py` policy to follow when
implementation is approved to proceed.

## Problem

The project uses a `src/` layout (`src/mrv/...`), per `CLAUDE.md`'s
repository structure. Inside `pytest`, imports resolve because the root
`conftest.py` inserts `src/` into `sys.path` — but that shim only takes
effect within the `pytest` process.

Running a module directly does **not** go through `conftest.py`, so e.g.:

```
python -m mrv.data_collection.collect
```

fails with `ModuleNotFoundError: No module named 'mrv'` unless the caller
manually sets `PYTHONPATH=src` (or the PowerShell/cmd equivalent) first.

This isn't specific to `collect.py` — every future entrypoint will hit the
same gap: `features` module scripts, the FastAPI app in `api/app/`, the
Streamlit app in `dashboard/`, and eventual Docker `CMD`/`ENTRYPOINT`
instructions under `infra/docker/`.

## Options considered

### Option A — Document `PYTHONPATH` usage

Add a note to `README.md`/`docs/setup/` instructing users to set
`PYTHONPATH=src` before running any `mrv` entrypoint directly.

- **Pros**: zero new files, no build-backend decision, smallest possible
  footprint right now.
- **Cons**:
  - Manual and easy to forget; shell-specific (bash vs. PowerShell vs.
    cmd.exe set env vars differently — real friction on a
    Windows-primary dev setup).
  - Has to be re-documented for every future entrypoint (features, api,
    dashboard, Docker) rather than solved once.
  - Leaves an "internal setup detail" leaking into how a reviewer or demo
    audience would need to run the system — not what "deployable and
    demoable" (CLAUDE.md) implies.

### Option B — Minimal `pyproject.toml` + `pip install -e .`

Add a small `pyproject.toml` declaring `mrv` as an installable package
(src-layout, `setuptools` backend), then run `pip install -e .` once in
the project venv.

- **Pros**:
  - `import mrv...` works everywhere after a one-time install — pytest,
    direct script runs, future `uvicorn`/`streamlit` entrypoints, Docker
    builds — no per-run environment variable.
  - Standard, idiomatic packaging for a `src/` layout Python project
    (that layout exists specifically to force proper installation
    instead of relying on cwd-based imports).
  - One-time setup cost instead of a recurring reminder repeated in every
    doc/script/Dockerfile from here on.
  - Makes `conftest.py`'s `sys.path` shim redundant — it could be removed
    once the package is installed (not done as part of this note; a
    follow-up implementation detail if Option B is approved).
- **Cons**:
  - One new file, and a small new decision (build backend — `setuptools`
    is the conservative default, ships with `pip`, no extra install).
  - Introduces package metadata (name, version placeholder) even though
    there's no current plan to publish to PyPI.

## Recommendation

**Option B.**

This project is explicitly scoped as portfolio-grade: "a working data →
model → API → dashboard → monitoring chain, deployable and demoable...
structured so it could plausibly become a climate-tech startup/competition
pitch" (`CLAUDE.md`). A reviewer or demo audience running any entrypoint
shouldn't need tribal knowledge of `PYTHONPATH` — that's exactly the kind
of rough edge that undermines "runs cleanly" credibility in a demo or
due-diligence context, distinct from just "tests pass."

It also scales better than Option A: every remaining module in the
roadmap (`features`, `api`, `dashboard`) will need the same import to
resolve, and Docker packaging — already in the approved tech stack,
`infra/docker/` — will hit this exact problem again. Fixing it once now,
via the mechanism the `src/` layout was already designed for, avoids
re-explaining `PYTHONPATH` in every subsequent module's docs and in the
eventual Dockerfile.

The cost is small and one-time: one new file (`pyproject.toml`), no new
runtime dependency (`setuptools` ships with `pip`), and it doesn't require
changing any application code — `collect.py` itself doesn't need to
change, only the environment setup step does.

**`conftest.py` policy**: keep `conftest.py` as-is for now; do not delete
or modify it in the first packaging implementation. Revisit removing its
`sys.path` shim only after `pyproject.toml` + `pip install -e .` is proven
to work end to end — treat that as a separate, later cleanup step, not
part of the initial packaging change.

## Approved minimal `pyproject.toml` outline

This is the exact shape to implement — **follow it exactly, no extra
fields, no extra packaging tools** (no `hatchling`/`flit`/`poetry`, no
optional-dependency groups, no scripts/entry-points section yet):

- `[build-system]`
  - `requires = ["setuptools>=61", "wheel"]`
  - `build-backend = "setuptools.build_meta"`
- `[project]`
  - `name = "mrv-carbon-monitoring"` (or similar — final string decided
    at implementation time, not a substantive choice)
  - `version = "0.1.0"`
  - `requires-python = ">=3.9"`
  - `dependencies` = the same core set as `requirements.txt` today:
    `earthengine-api`, `python-dotenv`, `pytest` — no additions.
- No extras yet: things like a scipy/geopandas stack or similar stay
  deferred, per CLAUDE.md's "no unapproved dependencies" rule — adding
  `pyproject.toml` is not a backdoor for pulling in packages that
  haven't been asked for separately.

## Not decided in this note (deferred to implementation, pending approval)

- Whether `requirements.txt` is kept alongside `pyproject.toml` (e.g. as
  a pinned/lock reference) or retired once `dependencies` in
  `pyproject.toml` is the source of truth.
- Any change to `collect.py` or other application code (none expected,
  per the outline above).
