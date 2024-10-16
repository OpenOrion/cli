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
    def assety_valid_remote_url(remote_url: str) -> None:
        try:
            repo = Repo(".")
            # Using ls-remote to check if the URL is valid and accessible
            repo.git.ls_remote(remote_url)
        except GitCommandError:
            raise AssertionError(f"Remote URL {remote_url} is not valid or accessible.")



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
    def push_repo(archive_path:Union[str, Path], branch_name: str = "main") -> None:
        """Pushes the branch to the remote repository, handles the first-time push."""
        VersionHelper.assert_git_configured()
        try:
            repo = Repo(archive_path)
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
    def commit_repo(
        archive_path:Union[str, Path],
        message: str,
        author_name: Optional[str] = None,
        author_email: Optional[str] = None,
    ) -> None:
        VersionHelper.assert_git_configured()
        try:
            repo = Repo(archive_path)
            if author_name and author_email:
                repo.git.commit(m=message, author=f"{author_name} <{author_email}>")
            else:
                repo.git.commit(m=message)
            logger.info("Changes committed successfully.")
        except GitCommandError as e:
            logger.error(f"Failed to commit changes: {str(e)}")

    @staticmethod
    def stage_repo(archive_path:Union[str, Path]) -> None:
        VersionHelper.assert_git_configured()
        try:
            repo = Repo(archive_path)
            repo.git.add(A=True)
            logger.info("Staged all changes.")
        except GitCommandError as e:
            logger.error(f"Failed to stage changes: {str(e)}")

    @staticmethod
    def initialize_repo(archive_path: Union[str, Path], remote_url: Optional[str] = None) -> None:
        """
        Initialize a new Git repository, configure user information, and make an initial commit.
        """

        VersionHelper.assert_git_configured()
        VersionHelper.assety_valid_remote_url(remote_url)
        
        try:
            # Initialize the repository
            repo = Repo.init(archive_path, initial_branch="main")
            logger.info("Git repository initialized with 'main' as the default branch.")

            if remote_url:
                repo.create_remote('origin', remote_url)
                logger.info(f"Remote 'origin' added with URL: {remote_url}")

            # Stage all files for the initial commit
            repo.git.add(A=True)  # Equivalent to 'git add .'
            logger.info("Staged all files for initial commit.")

        except GitCommandError as e:
            logger.error(f"Git command error: {e}")
        except Exception as e:
            logger.error(f"Error initializing Git repository: {e}")


