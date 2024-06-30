import os
import subprocess
import click
from .base_service import BaseService

class CreateService(BaseService):
    def create(self, name, path, step_file):
        """Create a new project"""
        project_path = os.path.join(path, name)

        try:
            # Create the new directory
            os.makedirs(project_path, exist_ok=True)
            click.echo(f"Project '{name}' has been created at {project_path}")

            # Initialize a new Git repository
            subprocess.run(["git", "init"], cwd=project_path, check=True)
            click.echo("Initialized a new Git repository")

            if step_file:
                self.generate(step_file, project_path, name)
                click.echo(f"Step file to be processed: {step_file}")
        except Exception as e:
            click.echo(f"Error: {e}")

