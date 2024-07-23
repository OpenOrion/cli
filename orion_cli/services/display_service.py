from pathlib import Path
import subprocess
from typing import Optional, Union
import click

from orion_cli.services.cad_service import CadService

class DisplayService:
    @staticmethod
    def display(project_path: Union[str, Path]):
        """Displays the current project"""
        try:
           project_path = Path(project_path)
           CadService.visualize_project(project_path, verbose=True)

        except Exception as e:
            click.echo(f"An unexpected error occurred: {e}")