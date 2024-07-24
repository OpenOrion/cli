import subprocess
from typing import Optional
import click
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
            click.echo("Changes committed successfully.")

            # Set branch name to 'main'
            current_branch = "main"

            # Attempt to push changes
            try:
                subprocess.check_call(["git", "push", "origin", current_branch])
            except subprocess.CalledProcessError:
                # If push fails, it might be because it's the first push
                click.echo("First push detected. Setting upstream branch...")
                subprocess.check_call(["git", "push", "-u", "origin", current_branch])

            click.echo("Deployment successful!")

        except subprocess.CalledProcessError as e:
            click.echo(f"An error occurred during deployment: {e}")
            click.echo("Please check your git configuration and try again.")
        except Exception as e:
            click.echo(f"An unexpected error occurred: {e}")