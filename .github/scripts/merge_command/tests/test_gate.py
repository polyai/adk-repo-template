from gate import approval_problems, check_problems


def pr_data(decision="APPROVED", threads=(), reviews=()):
    return {
        "reviewDecision": decision,
        "reviewThreads": {"nodes": [{"isResolved": r} for r in threads]},
        "latestReviews": {"nodes": list(reviews)},
    }


def test_review_decision():
    assert approval_problems(pr_data(), {}, "abc") == []
    assert [r for r, _ in approval_problems(pr_data("REVIEW_REQUIRED"), {}, "abc")] == [
        "Approval required"
    ]
    assert [r for r, _ in approval_problems(pr_data("CHANGES_REQUESTED"), {}, "abc")] == [
        "Changes requested"
    ]


def test_last_push_approval_and_threads_only_when_the_ruleset_asks():
    stale = pr_data(threads=[False], reviews=[{"state": "APPROVED", "commit": {"oid": "old"}}])
    assert approval_problems(stale, {}, "abc") == []
    assert approval_problems(
        stale,
        {"require_last_push_approval": True, "required_review_thread_resolution": True},
        "abc",
    ) == [
        ("Latest commit not approved", "Get the latest commit approved then comment `/poly-merge`"),
        ("Unresolved review threads", "Resolve review threads then comment `/poly-merge`"),
    ]


def test_check_problems_cover_required_checks_except_the_deploy_check():
    rollup = [
        {"__typename": "CheckRun", "name": "ci", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"__typename": "CheckRun", "name": "lint", "status": "IN_PROGRESS", "conclusion": None},
        {"__typename": "StatusContext", "context": "legacy", "state": "FAILURE"},
        {
            "__typename": "CheckRun",
            "name": "poly/deploy",
            "status": "QUEUED",
            "conclusion": None,
        },
        {
            "__typename": "CheckRun",
            "name": "optional",
            "status": "COMPLETED",
            "conclusion": "FAILURE",
        },
    ]
    required = ["ci", "lint", "legacy", "missing", "poly/deploy"]
    assert check_problems(rollup, required) == [
        ("Check `legacy` failed", "Fix failing checks then comment `/poly-merge`"),
        ("Check `lint` running", "Wait for checks then comment `/poly-merge`"),
        ("Check `missing` not reported", "Wait for checks then comment `/poly-merge`"),
    ]
