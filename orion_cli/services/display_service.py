from pathlib import Path
import subprocess
from typing import Union
from orion_cli.services.log_service import logger

from orion_cli.services.cad_service import CadService

class DisplayService:
    @staticmethod
    def display(project_path: Union[str, Path]):
        """Displays the current project"""
        try:
           project_path = Path(project_path)
           CadService.visualize_project(project_path, verbose=True)

        except Exception as e:
            logger.info(f"An unexpected error occurred: {e}")