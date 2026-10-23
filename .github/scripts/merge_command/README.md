# `/poly-merge`

Scripts for `/poly-merge`, which deploys a PR's projects and then merges it, in place of the merge queue. Setup is in [SETUP.md](../../../SETUP.md#merge-queue-or-poly-merge).

- `gate.py` checks that the PR may merge, and records the merge with `main` that the run deploys.
- `checkout-merge.sh` checks out that merge in each job.
- `finish.py` merges the PR in git and reports the result on it.
- `lib.py` holds the helpers they share.

Run the tests with:

```bash
uv run --no-project --python 3.14 --with pytest pytest .github/scripts/merge_command/tests
```
