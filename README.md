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

# Install the git hooks (ruff, prettier, ty and a JSON check, matching CI)
pre-commit install

# Sign in to Agent Studio
poly setup
```

`poly setup` asks for your region, signs you in through the browser and saves an API key to `~/.poly/credentials.json`. It also offers shell completion and AI agent skills for your coding agent. When it asks **Set up a project?**, choose **Skip for now**: the projects you work on are already in the repo. To sign in without the other steps, run `poly login --region <region>` instead.

The project you work on is at `agents/<account>/<project>/`. Run `poly` commands from that directory.

In VS Code, select the `.venv` interpreter: `Cmd+Shift+P` > **"Python: Select Interpreter"** > choose `.venv/bin/python`.

> **API keys in environment variables:** the ADK also reads `POLY_ADK_KEY_<REGION>` (`POLY_ADK_KEY_US`, `_UK`, `_EUW`, `_STUDIO`) and then `POLY_ADK_KEY`, before the credentials file. CI uses these. Locally you only need them to override the saved key.

## Adding a project

Only for a project that isn't in `agents/` yet. From the repo root:

```bash
poly init --base-path agents --region <region> --account_id <account> --project_id <project>
```

This pulls the project into `agents/<account>/<project>/`. Commit it on a branch and open a PR. CI finds projects by their `project.yaml`, so nothing else needs registering. Once it's merged, [set up the sync webhook](#agent-studio-webhook) for the project.

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

> **Warning:** If changes are made in Agent Studio and not synced to the repo, the next PR merge overwrites them. Without the webhook, run a sync after any branch is merged in the Agent Studio UI.

### Agent Studio webhook

Each project needs its own webhook so that publishing in Agent Studio starts a sync.

**1. Create a GitHub token.** Agent Studio uses it to send the dispatch. Create a fine-grained personal access token at [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new):

- **Resource owner:** the organisation that owns this repo, not your personal account. A token owned by your account can't see the repo.
- **Repository access:** Only select repositories, then this repo.
- **Repository permissions:** **Contents: Read and write**. The list is alphabetical, so Contents is below Actions, Administration and Checks. Leave everything else at No access.
- **Expiration:** syncs stop without an error when the token expires, so note the date.

If your organisation requires approval for fine-grained tokens, the token gets a 404 from GitHub until an admin approves it.

Check that the token can see the repo. This should print the repo name:

```bash
GH_TOKEN=<token> gh api repos/<owner>/<repo> --jq .full_name
```

**2. Store it as an Agent Studio secret.** Create a secret in the workspace that owns the project, in the project's region:

| Field          | Value                                                         |
| -------------- | ------------------------------------------------------------- |
| Name           | `github-sync-token`                                           |
| Type           | Single value                                                  |
| Value          | `Bearer <token>`, with `Bearer ` included and no quotes       |
| Project access | the project                                                   |

Agent Studio sends the value as the `Authorization` header exactly as stored.

**3. Add the webhook to the project.** In `agents/<account>/<project>/agent_settings/experimental_config.json`, add a top-level `webhooks` key. `on_draft_published` covers merges to main and `on_deployment.live` covers rollbacks; each takes a list:

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

If the file already has other keys, add `webhooks` alongside them. Keep the deployment under `deployment`: GitHub rejects a `client_payload` with more than 10 top-level properties.

Merge the change through a PR. The webhook takes effect when Deploy publishes it.

**4. Check it works.** Publish a change in Agent Studio. A Sync Projects run with the `repository_dispatch` event should start within a few seconds, and push an `Update from AS` commit to `main`.

The workflow runs on `project-publish-live` and `project-rollback-live`. GitHub accepts a dispatch with any other event type, such as a deployment to `pre-release`, but starts no run and reports no error. If a second dispatch for the same project arrives while a sync is still running, the second cancels the first and syncs both changes.

#### Troubleshooting

To test the token and the workflow without Agent Studio, send a dispatch yourself. A `204` response means GitHub accepted it, and a sync run starts:

```bash
curl -i -X POST https://api.github.com/repos/<owner>/<repo>/dispatches \
  -H "Authorization: Bearer <token>" \
  -H "Accept: application/vnd.github+json" \
  -d '{"event_type":"project-publish-live","client_payload":{"account_id":"<account>","project_id":"<project>","deployment":{}}}'
```

| Symptom                                                  | Cause                                                                                                                                                                                                               |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Publishing starts no run; the curl returns `404`         | The token can't see the repo: wrong resource owner, the repo isn't selected, or the token is waiting for organisation approval.                                                                                    |
| Publishing starts no run; the curl returns `204`         | The token is fine, so Agent Studio isn't sending it. Check the secret is named `github-sync-token`, is in the project's workspace and region, gives the project access, and holds `Bearer <token>`. Without the secret, Agent Studio sends the dispatch with no `Authorization` header. |
| The curl returns `401`                                   | The token is wrong or has expired.                                                                                                                                                                                  |
| The run fails at the GitHub App token step with `Invalid keyData` | `GH_APP_PRIVATE_KEY` isn't a valid key. Set it from the `.pem` file (see [GitHub App](#2-github-app)).                                                                                                   |
| The run fails at find-projects with `No projects found`  | The project isn't on `main` yet, or `account_id`/`project_id` in the dispatch don't match its `project.yaml`.                                                                                                       |

## Updating the ADK version

1. Update the version in `pyproject.toml`.
2. Run `uv pip install -e ".[dev]"` locally to check it installs.
3. Open a PR. Once it merges, Sync Projects re-syncs every project with the new ADK version.
4. Check the [ADK releases](https://github.com/polyai/adk/releases) for changelogs and breaking changes.

## Commands

Run `poly` commands from the project directory, `agents/<account>/<project>/`.

```bash
# Run tests for a project
pytest agents/<account>/<project>/

# Lint
ruff check agents/<account>/<project>/
ruff format --check agents/<account>/<project>/

# Push to an Agent Studio branch (CI does this automatically)
poly branch create $(git branch --show-current)
poly push

# Pull from Agent Studio
poly pull

# Sync infrastructure from the template (downstream repos only)
.github/scripts/sync-from-template.sh --apply
```

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
