# MIT License
#
# Copyright (c) 2025 Open Orion, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

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