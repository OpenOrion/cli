# tests/test_create_command.py
from orion_cli.helpers.config_helper import ConfigHelper
import pytest
import os
import logging
from pathlib import Path

@pytest.mark.usefixtures("create_project")
def test_create_command_create_repo(create_project: Path):
    project_path = create_project

    # Check if the file_name directory is a git repo
    assert os.path.isdir(project_path)
    assert os.path.isdir(os.path.join(project_path, '.git'))

@pytest.mark.usefixtures("create_project")
def test_create_command_no_changes_to_stage(create_project: Path):
    project_path = create_project
    os.chdir(project_path)
    git_status = os.system('git status --porcelain')
    assert git_status == 0

@pytest.mark.usefixtures("create_project")
def test_create_command_config_file(create_project: Path):
    project_path = create_project
    file_name = os.path.basename(project_path)
    config_file = os.path.join(project_path, 'config.yaml')

    assert os.path.isfile(config_file)

    # Load the config file
    config = ConfigHelper.load_config(config_file)
    print("config:", config)

    # Check if the config matches the expected values
    
    assert config.cad_path == str(file_name + '.step')
    assert config.name == file_name
    assert config.repo_url == None
    assert config.options.max_name_depth == 3
    assert config.options.normalize_axis == False
    assert config.options.include_assets == False
    assert config.options.use_references == True





