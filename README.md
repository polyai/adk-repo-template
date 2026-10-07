# adk-deployments

Template repository for ADK-managed agent projects.

## Setup

Requires Python 3.14+, [uv](https://github.com/astral-sh/uv), and the [PolyAI ADK](https://github.com/polyai/adk) ([docs](https://polyai.github.io/adk/)).

```bash
# Create and activate a virtual environment
uv venv --python=3.14 --seed
source .venv/bin/activate

# Install all dependencies (ADK, dev tools)
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Set your API key (add to ~/.zshrc or ~/.bashrc to make permanent)
export POLY_ADK_KEY=<your-key>
```

In VS Code, select the `.venv` interpreter: `Cmd+Shift+P` > **"Python: Select Interpreter"** > choose `.venv/bin/python`.

## Repository Structure

```
agents/
  <account>/
    <project>/          # Agent Studio project
.github/
  workflows/            # CI, deploy, sync, branch cleanup
  scripts/              # Shared shell + Python scripts for CI
```

## Development Workflow

### Making changes

1. Create a git branch and open a PR
2. CI runs lint, tests, and pushes changes to an Agent Studio branch (matching your git branch name) for testing
3. Merge via the merge queue — this merges the Agent Studio branch to AS main

### Pushing to Agent Studio locally

CI handles this automatically on every PR push, but if you want to push to an Agent Studio branch locally (e.g. to test before committing to GitHub), you can replicate what CI does:

```bash
# Create an AS branch matching your git branch and push to it
poly branch create $(git branch --show-current)
poly push
```

> **Note:** This is an ADK push to Agent Studio, not a git push. It syncs your local project files to the Agent Studio branch so you can test in Agent Studio.

### Syncing from Agent Studio

The **Sync Projects** workflow pulls the latest state from Agent Studio into the repo. It runs:

- when Agent Studio sends a dispatch after a publish or rollback (see below)
- nightly at 03:00 UTC
- when the ADK version in `pyproject.toml` changes
- manually, from the Actions tab

To have Agent Studio dispatch a sync, add this webhook to the project's `agent_settings/experimental_config.json`, under both `on_draft_published` (merges to main) and `on_deployment.live` (rollbacks):

```json
{
  "url": "https://api.github.com/repos/<owner>/<repo>/dispatches",
  "auth": { "header": "Authorization", "secret_name": "github-sync-token" },
  "payload_template": {
    "event_type": "project-{{deployment_type}}-{{client_env}}",
    "client_payload": {
      "account_id": "{{account_id}}",
      "project_id": "{{project_id}}",
      "deployment": "{{payload}}"
    }
  }
}
```

The `github-sync-token` secret in Agent Studio holds `Bearer <token>`, where the token is a fine-grained personal access token with **Contents: Read and write** on this repository only. An optional top-level `branch` picks the branch to sync into, and defaults to `main`. Keep the deployment under `deployment`: GitHub rejects a `client_payload` with more than 10 top-level properties.

The workflow runs on `project-publish-live` and `project-rollback-live`. GitHub accepts a dispatch with any other event type, such as a deployment to `pre-release`, but it starts no run and nothing reports an error. If a second dispatch for the same project and branch arrives while a sync is still running, the second cancels the first and syncs both changes.

> **Warning:** If changes are made in Agent Studio and not synced to the repo, the next PR merge will overwrite those changes. Without the webhook, run a sync after any branch is merged in the Agent Studio UI.

### Updating the ADK version

1. Update the version in `pyproject.toml` (e.g. `"polyai-adk==0.16.2"`)
2. Run `uv pip install -e ".[dev]"` locally to verify it works
3. Open a PR with the change — on merge, the sync workflow will automatically re-sync all projects with the new ADK version
4. Check the [ADK releases](https://github.com/polyai/adk/releases) for changelogs and breaking changes

## Commands

```bash
# Run tests for a project
pytest agents/<account>/<project>/

# Lint
ruff check agents/<account>/<project>/
ruff format --check agents/<account>/<project>/

# Push to AS branch locally (CI does this automatically)
poly branch create $(git branch --show-current)
poly push

# Pull from Agent Studio
poly pull

# Sync infrastructure from template (downstream repos only)
.github/scripts/sync-from-template.sh --apply
```

## Duplicating This Template for a New Deployment Repo

1. Create a new GitHub repo from this template
2. Configure repo-specific files (not kept in sync — each downstream repo owns them):
   - `pyproject.toml` — project name, ADK version pin, dev dependencies
   - `README.md` — repo-specific orientation
   - `.gitignore` — add any repo-specific ignores
3. Set up a [GitHub App](https://docs.github.com/en/apps/creating-github-apps) for CI authentication:
   - Create a GitHub App with **Contents: Read & write** permission
   - Install it on the repository
   - Add the following secrets:
     - `GH_APP_ID` — the GitHub App's App ID
     - `GH_APP_PRIVATE_KEY` — the GitHub App's private key (PEM format)
4. Set up ADK secrets (not copied from GitHub templates — must be added manually):
   - For a single region: set `POLY_ADK_KEY`
   - For multiple regions: set `POLY_ADK_KEY_EU`, `POLY_ADK_KEY_US`, `POLY_ADK_KEY_UK`, `POLY_ADK_KEY_STUDIO`
   - Generate keys at your region's Agent Studio settings page (e.g. `https://studio.us.poly.ai/settings/account`)
   - All changes will be attributed to the owner of the key
5. Protect `main` with merge queue enabled
6. Sync infrastructure updates from the template:
   ```bash
   .github/scripts/sync-from-template.sh            # preview
   .github/scripts/sync-from-template.sh --apply    # apply and commit
   ```
   Synced paths: `.github/`, `.pre-commit-config.yaml`

See [CONTRIBUTING.md](CONTRIBUTING.md) for the repo structure reference and decision trees.

## Updating the ADK Version

1. Update the version in `pyproject.toml`
2. Run `uv pip install -e ".[dev]"` locally to verify
3. Open a PR — on merge, the sync workflow automatically re-syncs all projects
4. Check the [ADK releases](https://github.com/polyai/adk/releases) for breaking changes
