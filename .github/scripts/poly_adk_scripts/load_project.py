import logging

from poly.project import AgentStudioProject

logging.getLogger("poly").setLevel(logging.WARNING)


def load_local_agent_studio_project(base_path: str, branch_name: str) -> AgentStudioProject:
    """Load an Agent Studio project from the given base path and switch to the specified branch.

    Args:
        base_path (str): The file path to the Agent Studio project.
        branch_name (str): The branch name to switch to.

    Returns:
        The loaded Agent Studio project.
    """
    project = AgentStudioProject.from_file_path(base_path)
    # Force branch id to be main
    project.branch_id = "main"
    _, branches = project.get_branches()
    if branch_id := branches.get(branch_name):
        project.branch_id = branch_id
        project.api_handler.switch_branch(branch_id)
    else:
        project.create_branch(branch_name)

    project.load_project()
    project._not_loaded_resources = []
    return project
