import logging
from typing import Any

from poly.project import AgentStudioProject

logging.getLogger("poly").setLevel(logging.WARNING)


def fetch_project_state(
    base_path: str, branch: str = "main"
) -> tuple[AgentStudioProject, dict[str, Any]]:
    """Open the project at base_path and fetch the remote state of an DS branch.

    Unlike load_local_agent_studio_project, a named branch that does not exist is
    a hard ValueError — no silent fallback to main. Fetch only rewrites the
    gitignored _gen/.agent_studio_config tracked state, not project files, so the
    result is ready for project_status() against what is on disk.

    Returns:
        The project and the fetched projection dict.
    """
    project = AgentStudioProject.from_file_path(base_path)
    # Set the branch before touching api_handler — it is a lazy property that
    # bakes in branch_id on first access.
    project.branch_id = "main"
    projection = project.fetch_project(branch_name=branch if branch != "main" else None)
    project._not_loaded_resources = []
    return project, projection


def load_local_agent_studio_project(base_path: str, branch_name: str) -> AgentStudioProject:
    """Load a Dialog Studio project from the given base path and switch to the specified branch.

    If the specified branch does not exist, the project will remain on the main branch.

    Args:
        base_path (str): The file path to the Dialog Studio project.
        branch_name (str): The branch name to switch to.

    Returns:
        The loaded Dialog Studio project.
    """
    project = AgentStudioProject.from_file_path(base_path)
    # Force branch id to be main
    project.branch_id = "main"
    _, branches = project.get_branches()
    if branch_meta := branches.get(branch_name):
        branch_id = branch_meta["branchId"]
        project.branch_id = branch_id
        project.api_handler.switch_branch(branch_id)

    project.load_project()
    project._not_loaded_resources = []
    return project
