# Contributing

## Repository Structure

```
<root>/                             # e.g. agents/ (template) or <client>/ (downstream)
  <account>/
    <project>/                      # One Dialog Studio project
      project.yaml                  # DS project definition
      ...                           # Flows, functions, tests
.github/
  workflows/
    ci.yml                          # PR lint, test, push to DS branch
    actionlint.yml                  # Lint workflows on PRs that change .github/
    deploy.yml                      # Merge queue: merge DS branch to DS main
    merge-command.yml               # /poly-merge: deploy and merge a PR from a comment
    deploy-check.yml                # Sets the poly/deploy check on each PR head
    sync_projects.yml               # Pull from DS into git (DS dispatch, nightly, manual, ADK bump)
    delete-as-branch-on-pr-close.yml
    delete-as-branch-on-commit-removes-project.yml
  scripts/
    detect-changed-dirs.sh          # Find which projects changed in a commit range
    lint-and-test.sh                # Lint, format-check, type-check and test projects
    deploy-project.sh               # Push a project to its DS branch and merge it
    run-tests.sh                    # Run pytest for changed projects
    format-project.sh               # Formatting applied after every pull from DS
    pre-commit-format.sh            # Pre-commit hook: format-project.sh on staged projects
    sync-from-template.sh           # Pull infra updates from template repo
    poly_adk_scripts/               # ADK operations (push, pull, merge, validate)
    merge_command/                  # /poly-merge: gate, finish, checkout of the merge, tests
pyproject.toml                      # Python deps, ruff/ty/pytest config
.pre-commit-config.yaml             # Pre-commit hooks (synced from template)
```

---

## Decision Trees

### Where does my change go?

```
Is it an agent project change (flows, functions, prompts, tests)?
├─ Yes → <root>/<account>/<project>/
│        Branch, PR, CI pushes to DS branch, merge queue or /poly-merge merges to DS main.
│
Is it a CI/CD or script change?
├─ Yes, and it should apply to ALL deployment repos
│  → Change it in adk-repo-template (the template), then sync downstream.
├─ Yes, but it's specific to THIS repo
│  → Change it here, but be aware sync-from-template.sh will overwrite
│    .github/. Move repo-specific logic into a non-synced location or
│    guard it.
│
Is it a tooling config change (ruff, pytest, ty)?
├─ Yes → pyproject.toml (not synced from template — each repo owns its config)
│
Is it a new project?
└─ Yes → Create <root>/<account>/<project>/ with a project.yaml.
         CI auto-discovers projects by finding project.yaml files.
```

---

## Writing Unit Tests

### Stubbing runtime modules

Each project's `_gen/` directory holds stubs of PolyAI runtime packages (`runtime`, `utils`, etc.). These stubs are auto-generated and not installable outside Dialog Studio, so tests must mock them in `sys.modules` **before** importing any function module.

The standard pattern:

```python
import sys
import types
from unittest.mock import MagicMock

_IMPORT_STUBS = [
    "utils",
    "utils.secret_vault",
    "runtime",
    "runtime.conv_utils",
    "runtime.conversation",
    "runtime.flow",
    # ... add others as needed
]

for name in _IMPORT_STUBS:
    if name not in sys.modules:
        if "." not in name:
            sys.modules[name] = types.ModuleType(name)
        else:
            parent = name.rsplit(".", 1)[0]
            if parent not in sys.modules:
                sys.modules[parent] = types.ModuleType(parent)
            sys.modules[name] = MagicMock()

# Now safe to import function modules
from functions.my_function import my_function  # noqa: E402
```

> **Important:** The stubs must run before any `from functions...` import. If you see `ModuleNotFoundError: No module named 'runtime'` (or `utils`, etc.) in CI, a stub is missing.

---

### How does code reach Dialog Studio?

```
Developer pushes to PR
  → CI detects changed projects (detect-changed-dirs.sh --depth 2)
  → CI creates/updates an DS branch matching the git branch name
  → Developer tests in DS on that branch

PR enters merge queue
  → deploy.yml runs lint+test again
  → Pushes final state to DS branch
  → Merges DS branch to DS main
  → Verifies DS branch is deleted

Or, with DEPLOY_MODE=command, someone comments /poly-merge on the PR
  → merge-command.yml checks access, approvals, required checks and conflicts (gate.py)
  → Waits for earlier /poly-merge runs that touch the same projects
  → Lints and tests the PR merged into main (lint-and-test.sh)
  → Pushes every project to its DS branch, then merges each into DS main (deploy-project.sh)
  → Squash-merges the PR and reports on it (finish.py)

Changes made directly in Dialog Studio?
  → Sync Projects runs on the Dialog Studio publish or rollback dispatch, if configured (see SETUP.md)
  → Otherwise run it manually; it also runs nightly and on an ADK version bump
  → Pulls from DS main, formats, commits to git main
  → WARNING: unsynced DS changes will be overwritten by the next PR merge
```

### When to sync from Dialog Studio vs. push from git

```
Did a human edit something in the Dialog Studio UI?
├─ Yes → Publishing syncs it automatically if the webhook is set up (see SETUP.md);
│        otherwise run the Sync Projects workflow to pull those changes into git.
│        Do this BEFORE merging any PRs that touch the same project.
│
Did you update the ADK version in pyproject.toml?
├─ Yes → Sync runs automatically on merge to main (watches pyproject.toml).
│
Normal development?
└─ Work in git. CI handles pushing to DS branches and merging.
```
