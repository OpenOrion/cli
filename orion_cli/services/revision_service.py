import logging
from pathlib import Path
import subprocess
from typing import Optional, Union
import click
from orion_cli.services.log_service import logger
from orion_cli.services.cad_service import CadService, ProjectOptions

class RevisionService:
    @staticmethod
    def show_changes(project_path: Union[str, Path]):
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

                logger.info("Changes detected:")
                total_changes = sum(len(files) for files in changes.values())
                logger.info(f"Total files changed: {total_changes}")

                for change_type, files in changes.items():
                    if files:
                        logger.info(f"{change_type.capitalize()} files ({len(files)}):")
                        for file in files[:5]:  # Show up to 5 files for each type
                            logger.info(f"  - {file}")
                        if len(files) > 5:
                            logger.info(f"  ... and {len(files) - 5} more")
            else:
                logger.info("No changes detected.")

        except subprocess.CalledProcessError as e:
            logger.info(f"Error checking git diff: {e}")
        except Exception as e:
            logger.info(f"Error: {e}")

    @staticmethod
    def revision(project_path: Union[str,Path], cad_path: Union[str,Path], project_options: Optional[ProjectOptions] = None):
        """Update the project structure and commit the changes"""
        from orion_cli.helpers.config_helper import ConfigHelper
        from orion_cli.helpers.remote_helper import RemoteHelper
        import shutil

        assert RemoteHelper.ensure_git_installed(), "Git is not installed. Please install Git and try again."
        assert RemoteHelper.ensure_git_configured(), (
            "Git user information is not configured. "
            "Please set your Git user name and email using the following commands:\n"
            'git config --global user.name "Your Name"\n'
            'git config --global user.email "you@example.com"'
        )

        project_path = Path(project_path)
        cad_path = Path(cad_path)

        assert cad_path.exists(), f"Error: CAD file not found at {cad_path}"

        try:
            logger.info(f"Revising project at {project_path} with CAD file {cad_path}")
            # Regenerate the project structure
            CadService.revise_project(project_path, cad_path, write=True, project_options=project_options, verbose=True)
            logger.info("Made it passed the revise project")
            # Load config
            config = ConfigHelper.load_config(project_path / "config.yaml")
            
            if str(cad_path) != config.cad_path:
                cad_file_path = project_path / config.cad_path
                if cad_file_path.exists():
                    cad_file_path.unlink()
                    logger.info(f"Deleted CAD file at {cad_file_path}")
                # Copy CAD file to project path
                shutil.copy(cad_path, project_path / Path(cad_path).name)
                logger.info(f"Copied CAD file to {project_path / Path(cad_path).name}")
                config.cad_path = Path(cad_path).name
                
                ConfigHelper.save_config(project_path / "config.yaml", config)

                logger.info(f"Updated CAD file path in config.yaml to {cad_path.name}")

            # Show changes before staging
            RevisionService.show_changes(project_path)

            subprocess.run(["git", "add", "."], cwd=project_path, check=True)
            logger.info("Changes staged.")


        except Exception as e:
            error_message = f"Error occurred while executing the revision: {e}"
            logger.info(error_message)
            logging.exception(error_message)
            
