import pytest
import os


def test_revised_project_structure(revise_project, robot_step_file):
    project_path = revise_project
    file_name = os.path.basename(robot_step_file)

    # Check that the project_path exists
    assert os.path.exists(project_path), f"Project path {project_path} does not exist."

    # Check for the existence of required folders and files
    required_items = [
        os.path.join(project_path, file_name),
        os.path.join(project_path, '.gitignore')
    ]

    for item in required_items:
        assert os.path.exists(item), f"Required item {item} does not exist in project path."
