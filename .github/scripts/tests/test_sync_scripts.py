"""Sync Projects finds every project, shares it out, and summarizes every project.

* Projects are agents/<account>/<project>; filters pick by project.yaml IDs.
* Finding none is fine unless a filter named the projects to sync.
* A runner per 40 projects, at most 16, and never more runners than projects.
* The summary covers every project: one without a result counts as failed,
  and failures fail the job while skipped or superseded projects do not.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import find_projects  # noqa: E402
import sync_summary  # noqa: E402


def make_projects(root: Path, count: int, account: str = "acme") -> None:
    for i in range(count):
        project = root / "agents" / account / f"proj{i:03d}"
        project.mkdir(parents=True)
        (project / "project.yaml").write_text(f"account_id: {account}\nproject_id: proj{i:03d}\n")


def outputs(tmp_path, monkeypatch, **env) -> dict:
    out = tmp_path / "out.txt"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    for name in ("INPUT_ACCOUNT_ID", "INPUT_PROJECT_ID"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    code = find_projects.main()
    values = (
        dict(line.split("=", 1) for line in out.read_text().splitlines()) if out.exists() else {}
    )
    return {"code": code, **values}


@pytest.mark.parametrize("count, shards", [(1, 1), (40, 1), (41, 2), (549, 14), (700, 16)])
def test_shards_scale_with_the_project_count(tmp_path, monkeypatch, count, shards):
    make_projects(tmp_path, count)
    result = outputs(tmp_path, monkeypatch)
    assert result["code"] == 0
    assert len(json.loads(result["projects"])) == count
    assert json.loads(result["shards"]) == list(range(shards))


def test_filters_pick_by_project_yaml(tmp_path, monkeypatch):
    make_projects(tmp_path, 3, "acme")
    make_projects(tmp_path, 2, "other")
    result = outputs(tmp_path, monkeypatch, INPUT_ACCOUNT_ID="other", INPUT_PROJECT_ID="proj001")
    assert json.loads(result["projects"]) == ["other/proj001"]
    assert json.loads(result["shards"]) == [0]


def test_no_projects_is_fine_unless_a_filter_named_some(tmp_path, monkeypatch):
    (tmp_path / "agents").mkdir()
    assert outputs(tmp_path, monkeypatch)["has_projects"] == "false"
    assert outputs(tmp_path, monkeypatch, INPUT_PROJECT_ID="missing")["code"] == 1


def write(path: Path, *results: dict) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in results))


def test_summary_merges_shards_and_reports_missing_projects(tmp_path):
    write(
        tmp_path / "shard-0.jsonl",
        {"project": "a/x", "status": "committed", "message": "abc123"},
        {"project": "a/y", "status": "no_change", "message": ""},
    )
    write(
        tmp_path / "shard-1.jsonl",
        {"project": "b/z", "status": "failed", "message": "Pull failed: 403"},
    )

    results = sync_summary.load(tmp_path, ["a/x", "a/y", "b/z", "b/missing"])
    summary = sync_summary.summarize(results)

    assert results["b/missing"]["status"] == "failed"
    assert "### ❌ Failed (2)" in summary
    assert "| `b/z` | Pull failed: 403 |" in summary
    assert "➖ 1 project(s) unchanged" in summary


def test_summary_fails_only_on_failures(tmp_path, monkeypatch):
    write(
        tmp_path / "shard-0.jsonl",
        {"project": "a/x", "status": "superseded", "message": "changed during its sync"},
    )
    monkeypatch.setattr(sys, "argv", ["sync_summary.py", str(tmp_path)])
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setenv("PROJECTS_JSON", json.dumps(["a/x"]))
    assert sync_summary.main() == 0
    monkeypatch.setenv("PROJECTS_JSON", json.dumps(["a/x", "a/y"]))
    assert sync_summary.main() == 1
