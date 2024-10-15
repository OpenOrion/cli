from pathlib import Path
import subprocess
from typing import Optional, Union
from orion_cli.models.archive import ArchiveConfig
from orion_cli.utils.logging import logger
from orion_cli.services.archive_service import ArchiveService
from orion_cli.helpers.remote_helper import VersionHelper


class ArchiveVersionService:
    @staticmethod
    def initialize(
        name: str,
        path: Union[str, Path],
        cad_path: Union[str, Path],
        remote_url: Optional[str] = None,
        include_assets: bool = False,
        author_name: Optional[str] = None,
        author_email: Optional[str] = None,
    ):
        """Create a new archive"""
        assert (
            VersionHelper.assert_git_installed()
        ), "Git is not installed. Please install Git and try again."
        assert VersionHelper.assert_git_configured(), (
            "Git user information is not configured. "
            "Please set your Git user name and email using the following commands:\n"
            'git config --global user.name "Your Name"\n'
            'git config --global user.email "you@example.com"'
        )

        cad_archive_path = Path(path) / name
        cad_path = Path(cad_path).resolve()

        # Create and save archive config
        archive_config = ArchiveConfig(
            name=name,
            cad_path=cad_path.name,
            repo_url=remote_url,
            include_assets=include_assets,
        )

        # Create the archive using CadService
        cad_archive = ArchiveService.create_archive(
            archive_path=cad_archive_path,
            cad_file=cad_path,
            config=archive_config,
            verbose=True,
        )

        # Initialize a new Git repository
        subprocess.run(
            ["git", "init", "--initial-branch=main"], cwd=cad_archive_path, check=True
        )
        logger.info("Git repository initialized")

        if author_name:
            subprocess.run(
                ["git", "config", "user.name", author_name],
                cwd=cad_archive_path,
                check=True,
            )
            author_email = author_email or "<>"
            subprocess.run(
                ["git", "config", "user.email", author_email],
                cwd=cad_archive_path,
                check=True,
            )
            logger.info("Added author information")

        # Make initial commit
        subprocess.run(["git", "add", "."], cwd=cad_archive_path, check=True)

        return cad_archive

    @staticmethod
    def deploy(deploy_msg: str = ""):
        """Commit staged changes and deploy the archive to the remote repository"""
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
    def show_changes(cad_archive_path: Union[str, Path]):
        """Show a summary of changes in the archive directory before staging"""
        from collections import defaultdict

        cad_archive_path = Path(cad_archive_path)

        try:
            # Get the list of changed files
            result = subprocess.run(
                ["git", "diff", "--name-status"],
                cwd=cad_archive_path,
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
                    cwd=cad_archive_path,
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
        archive_path: Union[str, Path],
        new_cad_path: Union[str, Path],
    ):
        """Update the archive structure and commit the changes"""
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

        archive_path = Path(archive_path)
        new_cad_path = Path(new_cad_path)

        assert new_cad_path.exists(), f"Error: CAD file not found at {new_cad_path}"

        try:
            logger.info(
                f"Revising archive at {archive_path} with CAD file {new_cad_path}"
            )
            # Regenerate the archive structure
            ArchiveService.revise_archive(
                archive_path,
                new_cad_path,
                write=True,
                verbose=True,
            )
            logger.info("Made it passed the revise archive")

            # Show changes before staging
            ArchiveVersionService.show_changes(archive_path)

            subprocess.run(["git", "add", "."], cwd=archive_path, check=True)
            logger.info("Changes staged.")

        except Exception as e:
            error_message = f"Error occurred while executing the revision: {e}"
            logger.info(error_message)
            logger.exception(error_message)
