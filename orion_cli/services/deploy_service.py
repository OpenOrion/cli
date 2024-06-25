import subprocess
from typing import Optional
import click

class DeployService:
    @staticmethod
    def deploy(deploy_msg: str = ""):
        """Commit staged changes and deploy the project to the remote repository"""
        try:
            # Commit changes
            subprocess.check_call(["git", "commit", "-m", deploy_msg])
            click.echo("Changes committed successfully.")

            # Get current branch name
            current_branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                universal_newlines=True
            ).strip()

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