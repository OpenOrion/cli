import pytest
import os
from click.testing import CliRunner
from orion_cli.cli import cli
from pathlib import Path
import shutil

# tests/conftest.py

@pytest.fixture(scope="module")
def robot_step_file():
    test_data_dir = Path(__file__).resolve().parent / 'test_data/step'
    step_file = test_data_dir / 'Robot.step'
    return step_file

@pytest.fixture(scope="module")
def module_tmp_path(tmp_path_factory):
    return tmp_path_factory.mktemp("module_tmp")

@pytest.fixture(scope="module")
def create_project(module_tmp_path: Path, robot_step_file: Path):
    project_name = robot_step_file.stem

    runner = CliRunner()
    result = runner.invoke(cli, ['create'], input=f'{project_name}\n{robot_step_file}\nN\n')
    assert result.exit_code == 0

    # Move the created project directory to the temporary path
    project_path = module_tmp_path / project_name
    shutil.move(project_name, project_path)

    yield project_path

    # Clean up the created project
    if project_path.exists():
        shutil.rmtree(project_path)

@pytest.fixture(scope="module")
def revise_project(create_project):
    project_path = create_project

    # Change the current working directory to the project path
    os.chdir(project_path)
    
    try:
        runner = CliRunner()
        result = runner.invoke(cli, ['revision'], input='y\n')
        print(f"CLI revise command exit code: {result.exit_code}")
        print(f"CLI revise command output: {result.output}")
        assert result.exit_code == 0
    except Exception as e:
        print(f"Error revising project: {e}")

    yield project_path
