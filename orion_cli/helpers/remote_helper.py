from collections import defaultdict
from pathlib import Path
from typing import Optional, Union
from orion_cli.utils.logging import logger
import git
from git import Repo, GitCommandError, InvalidGitRepositoryError

class VersionHelper:
    @staticmethod
    def get_remote_url() -> Optional[str]:
        try:
            repo = Repo(".")
            remote_url = repo.remotes.origin.url
            return remote_url.strip()
        except (InvalidGitRepositoryError, AttributeError):
            logger.info("No remote URL found.")
            return None

    @staticmethod
    def validate_remote_url(remote_url: str) -> bool:
        try:
            repo = Repo(".")
            # Using ls-remote to check if the URL is valid and accessible
            repo.git.ls_remote(remote_url)
            return True
        except GitCommandError:
            return False

    @staticmethod
    def assert_git_installed() -> bool:
        git_version = git.Git().version_info
        assert (
            git_version is not None
        ), "Git is not installed. Please install Git and try again."

    @staticmethod
    def assert_git_configured() -> None:
        VersionHelper.assert_git_installed()
        try:
            repo = Repo(".")
            user_name = repo.config_reader().get_value("user", "name", None)
            user_email = repo.config_reader().get_value("user", "email", None)
            assert bool(user_name) and bool(user_email), (
                "Git user information is not configured. "
                "Please set your Git user name and email using the following commands:\n"
                'git config --global user.name "Your Name"\n'
                'git config --global user.email "you@example.com"'
            )

        except (GitCommandError, InvalidGitRepositoryError):
            raise AssertionError("Git repository not found or Git command failed.")

    @staticmethod
    def push(branch_name: str = "main") -> None:
        """Pushes the branch to the remote repository, handles the first-time push."""
        try:
            repo = Repo(".")
            if not repo.remotes:
                raise AssertionError(
                    "No remote repository configured. Please add a remote."
                )

            remote = repo.remotes.origin

            # Check if the branch has an upstream tracking branch
            active_branch = repo.active_branch
            tracking_branch = active_branch.tracking_branch()

            if tracking_branch is None:
                # No upstream set, first-time push
                logger.info(f"First-time push, setting upstream for {branch_name}...")
                remote.push(refspec=f"{branch_name}:{branch_name}", set_upstream=True)
                logger.info(f"Branch {branch_name} pushed and upstream set.")
            else:
                # Push normally if upstream is already set
                logger.info(f"Pushing changes to {branch_name}...")
                remote.push(refspec=branch_name)

        except (InvalidGitRepositoryError, GitCommandError) as e:
            logger.error(f"Failed to push: {str(e)}")

    @staticmethod
    def show_changes(archive_path: Union[str, Path]):
        """Show a summary of changes in the archive directory before staging"""
        archive_path = Path(archive_path)

        try:
            # Initialize the repository
            repo = Repo(archive_path)

            if repo.is_dirty(untracked_files=True):
                changes = defaultdict(list)

                # Get the list of changed files (staged and unstaged)
                diff_index = repo.index.diff(None)  # Unstaged changes
                for diff_item in diff_index:
                    if diff_item.change_type == "M":
                        changes["modified"].append(diff_item.a_path)
                    elif diff_item.change_type == "A":
                        changes["added"].append(diff_item.a_path)
                    elif diff_item.change_type == "D":
                        changes["deleted"].append(diff_item.a_path)

                # Get the untracked files
                untracked_files = repo.untracked_files
                changes["untracked"] = untracked_files

                # Log the changes detected
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

        except InvalidGitRepositoryError:
            logger.error(f"The directory {archive_path} is not a valid git repository.")
        except GitCommandError as e:
            logger.error(f"Git command error: {e}")
        except Exception as e:
            logger.error(f"Error: {e}")



    @staticmethod
    def initialize_repo(cad_archive_path: Union[str, Path], author_name: Optional[str] = None, author_email: Optional[str] = None):
        """
        Initialize a new Git repository, configure user information, and make an initial commit.
        """
        cad_archive_path = Path(cad_archive_path)

        try:
            # Initialize the repository
            repo = Repo.init(cad_archive_path, initial_branch='main')
            logger.info("Git repository initialized with 'main' as the default branch.")
            
            # Configure author name and email if provided
            if author_name:
                with repo.config_writer() as git_config:
                    git_config.set_value("user", "name", author_name)
                    author_email = author_email or "<>"
                    git_config.set_value("user", "email", author_email)
                logger.info(f"Added author information: {author_name} <{author_email}>")
            
            # Stage all files for the initial commit
            repo.git.add(A=True)  # Equivalent to 'git add .'
            logger.info("Staged all files for initial commit.")
            
        except GitCommandError as e:
            logger.error(f"Git command error: {e}")
        except Exception as e:
            logger.error(f"Error initializing Git repository: {e}")
