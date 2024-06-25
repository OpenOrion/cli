import logging
from pathlib import Path
import subprocess
from typing import Optional, Union
import click

from orion_cli.services.cad_service import CadService, ProjectOptions
from .base_service import BaseService

class RevisionService(BaseService):
    def show_changes(self, project_path: Union[str, Path]):
        """Show a summary of changes in the project directory before staging"""
        from collections import defaultdict
        project_path = Path(project_path)

        try:
            # Get the list of changed files
            result = subprocess.run(
                ["git", "diff", "--name-status"],
                cwd=project_path,
                check=True,
                capture_output=True,
                text=True
            )

            if result.stdout:
                changes = defaultdict(list)
                for line in result.stdout.splitlines():
                    status, filename = line.split(maxsplit=1)
                    if status == 'M':
                        changes['modified'].append(filename)
                    elif status == 'A':
                        changes['added'].append(filename)
                    elif status == 'D':
                        changes['deleted'].append(filename)

                # Get untracked files
                untracked_result = subprocess.run(
                    ["git", "ls-files", "--others", "--exclude-standard"],
                    cwd=project_path,
                    check=True,
                    capture_output=True,
                    text=True
                )
                changes['untracked'] = untracked_result.stdout.splitlines()

                click.echo("Changes detected:")
                total_changes = sum(len(files) for files in changes.values())
                click.echo(f"Total files changed: {total_changes}")

                for change_type, files in changes.items():
                    if files:
                        click.echo(f"{change_type.capitalize()} files ({len(files)}):")
                        for file in files[:5]:  # Show up to 5 files for each type
                            click.echo(f"  - {file}")
                        if len(files) > 5:
                            click.echo(f"  ... and {len(files) - 5} more")
            else:
                click.echo("No changes detected.")

        except subprocess.CalledProcessError as e:
            click.echo(f"Error checking git diff: {e}")
        except Exception as e:
            click.echo(f"Error: {e}")

    def revision(self, project_path: Union[str,Path], cad_path: Union[str,Path], project_options: Optional[ProjectOptions] = None):
        """Update the project structure and commit the changes"""
        project_path = Path(project_path)
        cad_path = Path(cad_path)

        assert cad_path.exists(), f"Error: CAD file not found at {cad_path}"

        try:
            click.echo(f"Revising project at {project_path} with CAD file {cad_path}")
            # Regenerate the project structure
            CadService.revise_project(project_path, cad_path, write=True, project_options=project_options, verbose=True)

            # Show changes before staging
            self.show_changes(project_path)

            # Prompt user to continue with staging
            if click.confirm("Do you want to stage these changes?", default=True):
                # Git add and commit
                subprocess.run(["git", "add", "."], cwd=project_path, check=True)
                click.echo("Changes staged.")
            else:
                click.echo("Changes not staged.")
        except Exception as e:
            click.echo(f"Error: {e}")
