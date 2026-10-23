# Setting up a new repo from this template

Repo admins do this once. Work through the steps in order; the last one checks that everything is connected. For day-to-day work in the repo, see the [README](README.md).

## 1. Create the repo

Create a new GitHub repo from this template, then set up the files each repo owns. These aren't synced from the template:

- `pyproject.toml`: project name, ADK version pin, dev dependencies
- `README.md`: repo-specific orientation
- `.gitignore`: any repo-specific ignores

These come from the template but belong to the template repo itself. Replace them with your own or delete them:

- `CODEOWNERS`: names the template's maintainers
- `.github/ISSUE_TEMPLATE/`: issue forms for reporting problems with the template
- `SECURITY.md`: how to report security problems in the template

## 2. GitHub App

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

## 3. ADK keys

Add repo secrets with Dialog Studio API keys for CI. Generate keys at your region's Dialog Studio settings page (for example `https://studio.us.poly.ai/settings/account`). Changes CI makes are attributed to the key's owner.

- For a single region: `POLY_ADK_KEY`.
- For several regions: `POLY_ADK_KEY_US`, `POLY_ADK_KEY_UK`, `POLY_ADK_KEY_EUW` and `POLY_ADK_KEY_STUDIO`, as needed.

CI passes these to the ADK as environment variables. For a project, the ADK uses its region's key if it's set, and `POLY_ADK_KEY` otherwise.

## 4. Protect `main`

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
  - **Require status checks to pass**, with the check **`Verify all CI jobs passed or were skipped`** from GitHub Actions. CI reports this check on the pull request and Deploy reports it in the merge queue, so this one check gates both. Without it, the queue merges without waiting for Deploy to merge the Dialog Studio branch.
  - **Require merge queue**, with merge method **Squash**, build concurrency **1**, minimum and maximum group size **1**, and **Only merge non-failing pull requests**. Leave this out if you use `/poly-merge` instead (below).

GitHub suggests check names from recent runs. If it isn't suggested yet, type the name exactly.

### Merge queue or `/poly-merge`

PRs that change a project merge one of two ways. Both lint, test and deploy the PR merged into `main`, with the same steps.

- **Merge queue** (the default): add the PR to the queue. GitHub offers merge queues on public repos, and on private repos only in organisations on GitHub Enterprise Cloud.
- **`/poly-merge`**: comment `/poly-merge` on the PR. It works on any plan, and PRs that change different projects deploy at the same time.

To use `/poly-merge`:

1. **Choose which App merges** (see below), and give it **Checks**, **Issues**, **Pull requests** and **Workflows**, all **Read and write**, as well as **Contents**.
2. **Turn it on:**

   ```bash
   gh variable set DEPLOY_MODE --body command
   ```

3. **In the ruleset**, leave out **Require merge queue**, and add **`poly/deploy`** as a second required check, with the merging App as its source.

Each PR head then gets a `poly/deploy` check, which only the merging App can set. It waits for `/poly-merge` when the PR changes a project, and passes when it doesn't. PRs opened before the setup need a new push to get it.

#### Which App merges

- **One App (simplest).** Use the sync App from [step 2](#2-github-app).
- **Two Apps.** Create a separate merge App the same way, and add its credentials as `MERGE_APP_ID` and `MERGE_APP_PRIVATE_KEY`. `/poly-merge` uses them when they're set, and the sync App's otherwise. Don't add the merge App to the ruleset's bypass list.

With two Apps, the sync App keeps only Contents. And because the merge App doesn't bypass the ruleset, GitHub itself checks approvals and required checks when it merges. With one App, `/poly-merge` checks them before merging.

#### Optional: limit the App keys to `main`

By default the App credentials are repo secrets, so a workflow on any branch can use them. Anyone with write access could push a workflow on a branch that pushes straight to `main` or sets `poly/deploy` itself. To prevent that, keep the keys in an environment only `main` can use:

1. Create an environment, for example `apps`, in **Settings > Environments**, and limit its deployment branches to `main`.
2. Set the repo variable `APP_ENVIRONMENT` to its name. Every job that creates an App token then uses it.
3. Move the credentials into the environment, then delete the repo secrets:

   ```bash
   gh secret set GH_APP_ID --env apps --body <app-id>
   gh secret set GH_APP_PRIVATE_KEY --env apps < path/to/app.private-key.pem
   gh secret delete GH_APP_ID
   gh secret delete GH_APP_PRIVATE_KEY
   ```

   Do the same for `MERGE_APP_ID` and `MERGE_APP_PRIVATE_KEY` if you use two Apps.

Then run Sync Projects from `main`: to sync into another branch, pass it as the `branch` input, because a run started on the branch itself can't read the keys. The jobs don't create deployment records, and repo admins can still change the environment's rules.

## 5. Dialog Studio webhooks

Each project needs a webhook so that publishing in Dialog Studio starts a sync. Repeat these steps for every project, including ones added later.

**Create a GitHub token.** Create a [fine-grained personal access token](https://github.com/settings/personal-access-tokens/new) with:

- **Resource owner:** the organisation that owns this repo, not your personal account
- **Repository access:** only this repo
- **Repository permissions:** Contents: Read and write

Syncs stop without an error when the token expires, so note the expiry date.

**Store it in Dialog Studio.** In the project's workspace, create a secret:

| Field          | Value                                    |
| -------------- | ---------------------------------------- |
| Name           | `github-sync-token`                      |
| Type           | Single value                             |
| Value          | `Bearer <token>` (with the `Bearer ` prefix) |
| Project access | the project                              |

**Add the webhook.** Add a `webhooks` key to `agents/<account>/<project>/agent_settings/experimental_config.json`. `on_draft_published` fires on merges to main and `on_deployment.live` on rollbacks:

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

Merge it through a PR. Once Deploy publishes it, each publish or rollback in Dialog Studio starts a Sync Projects run, which pushes an `Update from AS` commit to `main`. If a second dispatch for the same project arrives while a sync is running, it cancels the first and syncs both changes.

## 6. Check it works

1. Open a PR that changes a project. CI should push to an Dialog Studio branch of the same name.
2. Merge it through the merge queue, or comment `/poly-merge`. That should merge the branch into Dialog Studio main, then merge the PR.
3. Publish a change in Dialog Studio. Sync Projects should push an `Update from AS` commit to `main`.

If a step fails, see [Troubleshooting](README.md#troubleshooting).
