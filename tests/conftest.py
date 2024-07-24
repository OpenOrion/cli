# tests/conftest.py
import pytest
import os
from click.testing import CliRunner
from orion_cli.cli import cli
from pathlib import Path
import shutil

@pytest.fixture(scope="module")
def robot_step_file():
    test_data_dir = os.path.join(os.path.dirname(__file__), 'test_data/step')
    step_file = os.path.join(test_data_dir, 'Robot.step')
    return step_file

@pytest.fixture(scope="module")
def module_tmp_path(tmp_path_factory):
    return tmp_path_factory.mktemp("module_tmp")

@pytest.fixture(scope="module")
def create_project(module_tmp_path: Path, robot_step_file: Path):
    file_name = os.path.basename(robot_step_file).split('.')[0]

    runner = CliRunner()
    result = runner.invoke(cli, ['create'], input=f'{file_name}\n{robot_step_file}\nN\n')
    assert result.exit_code == 0

    # Move the created project directory to the temporary path
    project_path = module_tmp_path / file_name
    shutil.move(file_name, project_path)

    yield project_path

    # Clean up the created project
    if os.path.exists(project_path):
        shutil.rmtree(project_path)

# @pytest.fixture(scope="module")
# def revise_project(create_project):
#     project_path = create_project
#     os.chdir(project_path)

#     runner = CliRunner()
#     result = runner.invoke(cli, ['revise'], input='y\n')
#     assert result.exit_code == 0

#     yield project_path
