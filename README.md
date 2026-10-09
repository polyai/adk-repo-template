# adk-deployments

Template repository for ADK-managed agent projects. Each project under `agents/` is an Agent Studio project, managed with the [PolyAI ADK](https://github.com/polyai/adk) ([docs](https://polyai.github.io/adk/)). Pull requests push changes to Agent Studio, and the merge queue merges them there. A sync workflow brings changes made in Agent Studio back into the repo.

- [Getting started](#getting-started): set up your machine to work on projects in an existing repo.
- [Adding a project](#adding-a-project): bring a project the repo doesn't have yet.
- [Development workflow](#development-workflow): how changes move between git and Agent Studio.
- [Syncing from Agent Studio](#syncing-from-agent-studio): the sync workflow and its webhook.
- [Setting up a new repo from this template](#setting-up-a-new-repo-from-this-template): one-off setup for repo admins.

## Getting started

Requires Python 3.14+ and [uv](https://github.com/astral-sh/uv).

```bash
# Create and activate a virtual environment
uv venv --python=3.14 --seed
source .venv/bin/activate

# Install the ADK and dev tools
uv pip install -e ".[dev]"

# Install the git hooks
pre-commit install

# Sign in to Agent Studio
poly setup
```

`poly setup` asks for your region, signs you in through the browser and saves an API key to `~/.poly/credentials.json`. It also offers shell completion and AI agent skills for your coding agent. When it asks **Set up a project?**, choose **Skip for now**: the projects you work on are already in the repo. To sign in without the other steps, run `poly login --region <region>` instead.

The project you work on is at `agents/<account>/<project>/`. Run `poly` commands from that directory.

The git hooks format each project you commit to with `.github/scripts/format-project.sh`, the same formatting a sync from Agent Studio applies, then run the ruff, ty and JSON checks CI runs. If the hook reformats files, the commit stops: add the changes and commit again. Commit with the virtual environment active, because the hooks use its `ruff`.

In VS Code, select the `.venv` interpreter: `Cmd+Shift+P` > **"Python: Select Interpreter"** > choose `.venv/bin/python`.

> **API keys in environment variables:** the ADK also reads `POLY_ADK_KEY_<REGION>` (`POLY_ADK_KEY_US`, `_UK`, `_EUW`, `_STUDIO`) and then `POLY_ADK_KEY`, before the credentials file. CI uses these. Locally you only need them to override the saved key.

## Adding a project

Only for a project that isn't in `agents/` yet. From the repo root:

```bash
poly init --base-path agents --region <region> --account_id <account> --project_id <project>
```

This pulls the project into `agents/<account>/<project>/`. A fresh pull isn't formatted the way CI expects, so format it before committing:

```bash
pre-commit run --all-files
```

Then commit it on a branch and open a PR. CI finds projects by their `project.yaml`, so nothing else needs registering. Once it's merged, [set up the sync webhook](#agent-studio-webhook) for the project.

## Repository structure

```
agents/
  <account>/
    <project>/          # Agent Studio project
.github/
  workflows/            # CI, deploy, sync, branch cleanup
  scripts/              # Shared shell + Python scripts for CI
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full structure and for writing unit tests.

## Development workflow

### Making changes

1. Create a git branch and open a PR.
2. CI runs lint and tests, then pushes your changes to an Agent Studio branch with the same name as your git branch, for testing.
3. Merge through the merge queue. Deploy merges the Agent Studio branch into Agent Studio main, which publishes the project.

### Pushing to Agent Studio locally

CI does this on every PR push. To try a change in Agent Studio before pushing to GitHub, do the same from the project directory:

```bash
poly branch create $(git branch --show-current)
poly push
```

> **Note:** `poly push` sends your local project files to the Agent Studio branch. It is not a git push.

## Syncing from Agent Studio

The **Sync Projects** workflow pulls the latest state from Agent Studio into the repo and pushes it to `main`. It runs:

- when Agent Studio sends a dispatch after a publish or rollback (see [Agent Studio webhook](#agent-studio-webhook))
- nightly at 03:00 UTC
- when the ADK version in `pyproject.toml` changes
- manually, from the Actions tab

> **Note:** A merge can't overwrite changes made in Agent Studio that haven't been synced yet. In the merge queue, Deploy checks that Agent Studio main matches git `main`, and fails the PR with `AS branch main is not in sync with git main` if a sync would change anything. Run Sync Projects for the project, then re-queue the PR. The webhook keeps the repo in sync, so this rarely happens.

### Agent Studio webhook

Each project needs a webhook so that publishing in Agent Studio starts a sync.

**1. Create a GitHub token.** Create a [fine-grained personal access token](https://github.com/settings/personal-access-tokens/new) with:

- **Resource owner:** the organisation that owns this repo, not your personal account
- **Repository access:** only this repo
- **Repository permissions:** Contents: Read and write

Syncs stop without an error when the token expires, so note the expiry date.

**2. Store it in Agent Studio.** In the project's workspace, create a secret:

| Field          | Value                                    |
| -------------- | ---------------------------------------- |
| Name           | `github-sync-token`                      |
| Type           | Single value                             |
| Value          | `Bearer <token>` (with the `Bearer ` prefix) |
| Project access | the project                              |

**3. Add the webhook.** Add a `webhooks` key to `agents/<account>/<project>/agent_settings/experimental_config.json`. `on_draft_published` fires on merges to main and `on_deployment.live` on rollbacks:

```json
{
  "webhooks": {
    "on_draft_published": [
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
    ],
    "on_deployment": {
      "live": [
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
      ]
    }
  }
}
```

Merge it through a PR. Once Deploy publishes it, each publish or rollback in Agent Studio starts a Sync Projects run, which pushes an `Update from AS` commit to `main`. If a second dispatch for the same project arrives while a sync is running, it cancels the first and syncs both changes.

#### Troubleshooting

| Symptom | Cause |
| ------- | ----- |
| Publishing starts no run | GitHub rejected the dispatch, usually because the token can't see the repo (its resource owner isn't the organisation, or the repo isn't selected) or the secret is missing, misnamed, or lacks the `Bearer ` prefix or project access. |
| A PR fails in the merge queue with `AS branch main is not in sync with git main` | Agent Studio has changes the repo doesn't. Run Sync Projects for the project, then re-queue. To merge anyway and overwrite the Agent Studio changes, add the `skip-as-sync-check` label and re-queue. |
| Sync Projects fails at the GitHub App token step with `Invalid keyData` | `GH_APP_PRIVATE_KEY` isn't a valid key. Set it from the `.pem` file (see [GitHub App](#2-github-app)). |
| Sync Projects fails at find-projects with `No projects found` | The project isn't on `main` yet, or the dispatch's `account_id`/`project_id` don't match its `project.yaml`. |

## Updating the ADK version

1. Update the version in `pyproject.toml`.
2. Run `uv pip install -e ".[dev]"` locally to check it installs.
3. Open a PR. Once it merges, Sync Projects re-syncs every project with the new ADK version.
4. Check the [ADK releases](https://github.com/polyai/adk/releases) for changelogs and breaking changes.

## Commands

From the repo root:

```bash
# Run tests for a project
pytest agents/<account>/<project>/

# Lint
ruff check agents/<account>/<project>/
ruff format --check agents/<account>/<project>/

# Sync infrastructure from the template (downstream repos only)
.github/scripts/sync-from-template.sh --apply
```

From the project directory, `agents/<account>/<project>/`:

```bash
# Push to an Agent Studio branch (CI does this automatically)
poly branch create $(git branch --show-current)
poly push

# Pull from Agent Studio
poly pull

# Chat with the agent on your Agent Studio branch, pushing local changes first
poly chat --push

# Call the agent with your microphone and speaker (needs a non-main branch)
poly call --push
```

`poly chat` talks to the last pushed state of your Agent Studio branch, and `--environment` picks another environment instead. `poly call` only reaches a branch's draft build, so run `poly branch create` first; it switches you to the new branch. Its audio dependencies come with the `dev` extras. See the ADK docs for [`poly chat`](https://polyai.github.io/adk/reference/cli/chat/), [`poly call`](https://polyai.github.io/adk/reference/cli/call/), [testing](https://polyai.github.io/adk/development/testing/) and the [full CLI reference](https://polyai.github.io/adk/reference/cli/).

## Setting up a new repo from this template

Repo admins do this once. Work through the steps in order; the last one checks that everything is connected.

### 1. Create the repo

Create a new GitHub repo from this template, then set up the files each repo owns. These aren't synced from the template:

- `pyproject.toml`: project name, ADK version pin, dev dependencies
- `README.md`: repo-specific orientation
- `.gitignore`: any repo-specific ignores

### 2. GitHub App

Sync Projects pushes to `main` with a GitHub App token, so its commits can bypass the branch rules.

1. In the organisation's settings, go to **Developer settings > GitHub Apps > New GitHub App**. Creating it in the organisation rather than your account means it doesn't depend on you.
   - **Name:** anything unique. Sync commits are authored as `<app-slug>[bot]`.
   - **Webhook:** untick **Active**.
   - **Repository permissions:** **Contents: Read and write**. Leave everything else at No access.
   - **Where can this GitHub App be installed?:** Only on this account.
2. **Install App**, and choose only this repo.
3. Under **Private keys**, click **Generate a private key**. GitHub downloads a `.pem` file.
4. Add the App's credentials as repo secrets. Set the key from the file, so its line breaks survive:

   ```bash
   gh secret set GH_APP_ID --body <app-id>
   gh secret set GH_APP_PRIVATE_KEY < path/to/app.private-key.pem
   ```

   `GH_APP_ID` is the numeric **App ID** at the top of the App's settings page, not the Client ID. Delete the `.pem` once the secret is set.

### 3. ADK keys

Add repo secrets with Agent Studio API keys for CI. Generate keys at your region's Agent Studio settings page (for example `https://studio.us.poly.ai/settings/account`). Changes CI makes are attributed to the key's owner.

- For a single region: `POLY_ADK_KEY`.
- For several regions: `POLY_ADK_KEY_US`, `POLY_ADK_KEY_UK`, `POLY_ADK_KEY_EUW` and `POLY_ADK_KEY_STUDIO`, as needed.

### 4. Protect `main`

**Pull request settings.** In **Settings > General > Pull Requests**:

- Allow **squash merging** only; untick merge commits and rebase merging. Each PR must land on `main` as a single commit: Sync Projects spots an ADK version change by comparing `main` with its previous commit.
- Set the default squash commit message to **Pull request title**.
- Tick **Automatically delete head branches**.

**Ruleset.** In **Settings > Rules > Rulesets**, create a branch ruleset:

- **Enforcement status:** Active.
- **Target branches:** the default branch.
- **Bypass list:** the GitHub App from step 2, set to **Exempt**, so Sync Projects can push straight to `main`.
- **Rules:**
  - **Restrict deletions.**
  - **Block force pushes.**
  - **Require a pull request before merging**, with allowed merge methods set to **Squash** only.
  - **Require status checks to pass**, with the check **`Verify all CI jobs passed or were skipped`** from GitHub Actions. CI reports this check on the pull request and Deploy reports it in the merge queue, so this one check gates both. Without it, the queue merges without waiting for Deploy to merge the Agent Studio branch.
  - **Require merge queue**, with merge method **Squash**, build concurrency **1**, minimum and maximum group size **1**, and **Only merge non-failing pull requests**.

GitHub suggests check names from recent runs. If it isn't suggested yet, type the name exactly.

### 5. Agent Studio webhooks

For each project, set up the [Agent Studio webhook](#agent-studio-webhook).

### 6. Check it works

1. Open a PR that changes a project. CI should push to an Agent Studio branch of the same name.
2. Merge it through the merge queue. Deploy should merge that branch into Agent Studio main.
3. Publish a change in Agent Studio. Sync Projects should push an `Update from AS` commit to `main`.

### Syncing infrastructure from the template

Downstream repos pick up workflow and hook changes from this template with:

```bash
.github/scripts/sync-from-template.sh            # preview
.github/scripts/sync-from-template.sh --apply    # apply and commit
```

This syncs `.github/` and `.pre-commit-config.yaml`.

## License

Apache License 2.0. See [LICENSE](LICENSE).
