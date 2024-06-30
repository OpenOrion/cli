import os
import subprocess
import click
from .base_service import BaseService

class RevisionService(BaseService):
    def revision(self, project_path, step_file, commit_message):
        """Update the project structure and commit the changes"""
        project_name = os.path.basename(project_path)

        try:
            # Regenerate the project structure
            self.generate(step_file, project_path, project_name)

            # Git add and commit
            subprocess.run(["git", "add", "."], cwd=project_path, check=True)
            subprocess.run(
                ["git", "commit", "-m", commit_message], cwd=project_path, check=True
            )
            click.echo(f"Changes committed with message: {commit_message}")
        except Exception as e:
            click.echo(f"Error: {e}")
