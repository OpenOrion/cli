from pathlib import Path
import subprocess
from typing import Union
import click

from orion_cli.helpers.cad_helper import CadHelper
from orion_cli.services.cad_service import AssemblyIndex, CadService, Project
from .base_service import BaseService

class RevisionService(BaseService):
    def revision(self, project_path: Union[str,Path], cad_path: Union[str,Path], commit_message: str):
        """Update the project structure and commit the changes"""
        project_path = Path(project_path)
        cad_path = Path(cad_path)

        assert cad_path.exists(), f"Error: CAD file not found at {cad_path}"

        try:
            # Regenerate the project structure
            CadService.revise_project(project_path, cad_path, write=True)

            # Git add and commit
            subprocess.run(["git", "add", "."], cwd=project_path, check=True)
            subprocess.run(
                ["git", "commit", "-m", commit_message], cwd=project_path, check=True
            )
            click.echo(f"Changes committed with message: {commit_message}")
        except Exception as e:
            click.echo(f"Error: {e}")
