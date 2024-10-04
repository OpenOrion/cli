import subprocess
from orion_cli.services.log_service import logger
from orion_cli.helpers.remote_helper import RemoteHelper

class DeployService:
    @staticmethod
    def deploy(deploy_msg: str = ""):
        """Commit staged changes and deploy the project to the remote repository"""
        assert RemoteHelper.ensure_git_installed(), "Git is not installed. Please install Git and try again."
        assert RemoteHelper.ensure_git_configured(), (
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