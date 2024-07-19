from pathlib import Path
import subprocess
from typing import Union
import click

from orion_cli.services.cad_service import CadService
from .base_service import BaseService

class CreateService(BaseService):
    def create(self, name: str, path: Union[str,Path], cad_path: Union[str,Path]):
        """Create a new project"""
        project_path = Path(path) / name
        if project_path.exists():
            click.echo(f"Error: Project '{name}' already exists at {project_path}")
            return
        cad_path = Path(cad_path)

        try:

            click.echo(f"Creating project '{name}' at {project_path}")

            CadService.create_project(project_path, cad_path)
            click.echo(f"Project '{name}' has been created at {project_path}")

            # Initialize a new Git repository
            subprocess.run(["git", "init"], cwd=project_path, check=True)
            click.echo("Initialized a new Git repository")


        except Exception as e:
            click.echo(f"Error: {e}")

