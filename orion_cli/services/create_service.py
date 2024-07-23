from pathlib import Path
import subprocess
from typing import Optional, Union
import click
import yaml
import shutil

from orion_cli.services.cad_service import CadService, ProjectOptions
from orion_cli.helpers.config_helper import ProjectConfig
from .base_service import BaseService

class CreateService(BaseService):
    def create(self, name: str, path: Union[str, Path], cad_path: Union[str, Path], remote_url: Optional[str] = None):
        """Create a new project"""
        
        project_path = Path(path) / name
        cad_path = Path(cad_path).resolve()

        try:
            click.echo(f"Creating project '{name}' at {project_path}")

            # Create the project using CadService
            CadService.create_project(
                project_path=project_path,
                cad_file=cad_path,
                project_options=ProjectOptions(),
                verbose=True
            )

            # Copy CAD file to project directory
            cad_file_name = cad_path.name
            project_step_file = project_path / cad_file_name
            shutil.copy2(cad_path, project_step_file)

            # Create and save project config
            project_config = ProjectConfig(
                name=name,
                cad_path=cad_file_name,
                repo_url=remote_url,
                options=ProjectOptions()
            )

            config_path = project_path / "config.yaml"
            with open(config_path, "w") as f:
                yaml.dump(project_config.model_dump(), f)

            click.echo(f"Project '{name}' has been created at {project_path}")
            click.echo(f"Configuration file created at {config_path}")

            # Initialize a new Git repository
            subprocess.run(["git", "init", "--initial-branch=main"], cwd=project_path, check=True)
            # Path to the template .gitignore file
            template_gitignore_path = Path(__file__).resolve().parent.parent / 'templates' / 'gitignore_template'

            # Read the content of the template .gitignore file
            gitignore_content = template_gitignore_path.read_text()

            # Write the content to the new project's .gitignore file
            (project_path / ".gitignore").write_text(gitignore_content)

            click.echo("Git repository initialized and .gitignore file created.")

            # Make initial commit
            subprocess.run(["git", "add", "."], cwd=project_path, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project_path, check=True)
            click.echo("Initial commit made.")

        except Exception as e:
            click.echo(f"Error: {e}")

