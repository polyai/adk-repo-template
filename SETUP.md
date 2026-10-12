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

Add repo secrets with Agent Studio API keys for CI. Generate keys at your region's Agent Studio settings page (for example `https://studio.us.poly.ai/settings/account`). Changes CI makes are attributed to the key's owner.

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
  - **Require status checks to pass**, with the check **`Verify all CI jobs passed or were skipped`** from GitHub Actions. CI reports this check on the pull request and Deploy reports it in the merge queue, so this one check gates both. Without it, the queue merges without waiting for Deploy to merge the Agent Studio branch.
  - **Require merge queue**, with merge method **Squash**, build concurrency **1**, minimum and maximum group size **1**, and **Only merge non-failing pull requests**.

GitHub suggests check names from recent runs. If it isn't suggested yet, type the name exactly.

## 5. Agent Studio webhooks

Each project needs a webhook so that publishing in Agent Studio starts a sync. Repeat these steps for every project, including ones added later.

**Create a GitHub token.** Create a [fine-grained personal access token](https://github.com/settings/personal-access-tokens/new) with:

- **Resource owner:** the organisation that owns this repo, not your personal account
- **Repository access:** only this repo
- **Repository permissions:** Contents: Read and write

Syncs stop without an error when the token expires, so note the expiry date.

**Store it in Agent Studio.** In the project's workspace, create a secret:

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

Merge it through a PR. Once Deploy publishes it, each publish or rollback in Agent Studio starts a Sync Projects run, which pushes an `Update from AS` commit to `main`. If a second dispatch for the same project arrives while a sync is running, it cancels the first and syncs both changes.

## 6. Check it works

1. Open a PR that changes a project. CI should push to an Agent Studio branch of the same name.
2. Merge it through the merge queue. Deploy should merge that branch into Agent Studio main.
3. Publish a change in Agent Studio. Sync Projects should push an `Update from AS` commit to `main`.

If a step fails, see [Troubleshooting](README.md#troubleshooting).
