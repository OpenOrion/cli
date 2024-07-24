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
    assert os.path.isdir(project_path), f"Project path {project_path} does not exist."
    assert os.path.isdir(os.path.join(project_path, '.git')), f"Project path {project_path} is not a git repository."

@pytest.mark.usefixtures("create_project")
def test_create_command_no_changes_to_stage(create_project: Path):
    project_path = create_project
    os.chdir(project_path)
    git_status = os.system('git status --porcelain')
    assert git_status == 0, f"Changes to stage in project path {project_path}."

@pytest.mark.usefixtures("create_project")
def test_create_command_config_file(create_project: Path):
    project_path = create_project
    file_name = os.path.basename(project_path)
    config_file = os.path.join(project_path, 'config.yaml')

    assert os.path.isfile(config_file), f"Config file {config_file} does not exist."

    # Load the config file
    config = ConfigHelper.load_config(config_file)
    print("config:", config)

    # Check if the config matches the expected values
    
    assert config.cad_path == str(file_name + '.step'), f"Config cad_path {config.cad_path} does not match expected value {file_name + '.step'}"
    assert config.name == file_name, f"Config name {config.name} does not match expected value {file_name}"
    assert config.repo_url == None, f"Config repo_url {config.repo_url} does not match expected value None"
    assert config.options.max_name_depth == 3, f"Config options.max_name_depth {config.options.max_name_depth} does not match expected value 3"
    assert config.options.normalize_axis == False, f"Config options.normalize_axis {config.options.normalize_axis} does not match expected value False"
    assert config.options.include_assets == False, f"Config options.include_assets {config.options.include_assets} does not match expected value False"
    assert config.options.use_references == True, f"Config options.use_references {config.options.use_references} does not match expected value True"





