from pathlib import Path
import subprocess
from typing import Optional, Union
from orion_cli.models.archive import ArchiveConfig
from orion_cli.utils.logging import logger
import shutil
from orion_cli.services.archive_service import ArchiveService, ArchiveOptions
from orion_cli.helpers.remote_helper import VersionHelper
from orion_cli.templates.README_template import README_TEMPLATE
from orion_cli.templates.gitignore_template import GITIGNORE_TEMPLATE


class ProjectService:
    @staticmethod
    def create(
        name: str,
        path: Union[str, Path],
        cad_path: Union[str, Path],
        remote_url: Optional[str] = None,
        include_assets: bool = False,
        author_name: Optional[str] = None,
        author_email: Optional[str] = None,
    ):
        """Create a new project"""
        assert (
            VersionHelper.assert_git_installed()
        ), "Git is not installed. Please install Git and try again."
        assert VersionHelper.assert_git_configured(), (
            "Git user information is not configured. "
            "Please set your Git user name and email using the following commands:\n"
            'git config --global user.name "Your Name"\n'
            'git config --global user.email "you@example.com"'
        )

        project_path = Path(path) / name
        cad_path = Path(cad_path).resolve()
        project_options = ArchiveOptions(include_assets=include_assets)

        logger.info(f"Creating project '{name}' at {project_path}")
        project_path.mkdir(parents=True, exist_ok=True)

        # Copy CAD file to project directory
        cad_file_name = cad_path.name
        project_step_file = project_path / cad_file_name
        shutil.copy2(cad_path, project_step_file)

        # Create and save project config
        project_config = ArchiveConfig(
            name=name,
            cad_path=cad_file_name,
            repo_url=remote_url,
            options=project_options,
        )

        config_path = project_path / "config.yaml"
        ConfigHelper.save_config(config_path, project_config)

        logger.info(f"Project '{name}' has been created at {project_path}")
        logger.info(f"Configuration file created at {config_path}")

        # Read the content of the template .gitignore file
        gitignore_content = GITIGNORE_TEMPLATE

        # Write the content to the new project's .gitignore file
        (project_path / ".gitignore").write_text(gitignore_content)

        # Create the project using CadService
        project = ArchiveService.create_archive(
            project_path=project_path,
            cad_path=cad_path,
            project_options=project_options,
            verbose=True,
        )

        # Create a README file
        cover_image_path = (
            f"./assets/{project.root_assembly.long_name}.svg"
            if include_assets
            else None
        )
        readme_content = README_TEMPLATE(name, remote_url, cover_image_path)
        (project_path / "README.md").write_text(readme_content)

        # Initialize a new Git repository
        subprocess.run(
            ["git", "init", "--initial-branch=main"], cwd=project_path, check=True
        )
        logger.info("Git repository initialized")

        if author_name:
            subprocess.run(
                ["git", "config", "user.name", author_name],
                cwd=project_path,
                check=True,
            )
            author_email = author_email or "<>"
            subprocess.run(
                ["git", "config", "user.email", author_email],
                cwd=project_path,
                check=True,
            )
            logger.info("Added author information")

        # Make initial commit
        subprocess.run(["git", "add", "."], cwd=project_path, check=True)

        return project

    @staticmethod
    def deploy(deploy_msg: str = ""):
        """Commit staged changes and deploy the project to the remote repository"""
        assert (
            VersionHelper.assert_git_installed()
        ), "Git is not installed. Please install Git and try again."
        assert VersionHelper.assert_git_configured(), (
            "Git user information is not configured. "
            "Please set your Git user name and email using the following commands:\n"
            'git config --global user.name "Your Name"\n'
            'git config --global user.email "you@example.com"'
        )
        try:
            # Commit changes
            subprocess.check_call(["git", "commit", "-m", deploy_msg])
            logger.info("Changes committed successfully.")

            # Set branch name to 'main'
            current_branch = "main"

            # Attempt to push changes
            try:
                subprocess.check_call(["git", "push", "origin", current_branch])
            except subprocess.CalledProcessError:
                # If push fails, it might be because it's the first push
                logger.info("First push detected. Setting upstream branch...")
                subprocess.check_call(["git", "push", "-u", "origin", current_branch])

            logger.info("Deployment successful!")

        except subprocess.CalledProcessError as e:
            logger.info(f"An error occurred during deployment: {e}")
            logger.info("Please check your git configuration and try again.")
        except Exception as e:
            logger.info(f"An unexpected error occurred: {e}")

    @staticmethod
    def display(project_path: Union[str, Path]):
        """Displays the current project"""
        try:
            project_path = Path(project_path)
            ArchiveService.visualize_archive(project_path, verbose=True)

        except Exception as e:
            logger.info(f"An unexpected error occurred: {e}")

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
                text=True,
            )

            if result.stdout:
                changes = defaultdict(list)
                for line in result.stdout.splitlines():
                    status, filename = line.split(maxsplit=1)
                    if status == "M":
                        changes["modified"].append(filename)
                    elif status == "A":
                        changes["added"].append(filename)
                    elif status == "D":
                        changes["deleted"].append(filename)

                # Get untracked files
                untracked_result = subprocess.run(
                    ["git", "ls-files", "--others", "--exclude-standard"],
                    cwd=project_path,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                changes["untracked"] = untracked_result.stdout.splitlines()

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
    def revision(
        project_path: Union[str, Path],
        cad_path: Union[str, Path],
        project_options: Optional[ArchiveOptions] = None,
    ):
        """Update the project structure and commit the changes"""
        from orion_cli.helpers.config_helper import ConfigHelper
        from orion_cli.helpers.remote_helper import VersionHelper
        import shutil

        assert (
            VersionHelper.assert_git_installed()
        ), "Git is not installed. Please install Git and try again."
        assert VersionHelper.assert_git_configured(), (
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
            ArchiveService.revise_archive(
                project_path,
                cad_path,
                write=True,
                project_options=project_options,
                verbose=True,
            )
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
            ProjectService.show_changes(project_path)

            subprocess.run(["git", "add", "."], cwd=project_path, check=True)
            logger.info("Changes staged.")

        except Exception as e:
            error_message = f"Error occurred while executing the revision: {e}"
            logger.info(error_message)
            logger.exception(error_message)
