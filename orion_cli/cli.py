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

from pathlib import Path
from typing import Optional, Union
import click
from orion_cli.services.display_service import DisplayService
from orion_cli.services.log_service import logger
from typing import Optional
import pkg_resources

version = pkg_resources.get_distribution("orion_cli").version

logo = """
  ____      _             _______   ____
 / __ \____(_)__  ___    / ___/ /  /  _/
/ /_/ / __/ / _ \/ _ \  / /__/ /___/ /  
\____/_/ /_/\___/_//_/  \___/____/___/ 
"""

click.echo(logo)


@click.group()
@click.version_option(version=version)
def cli():
    """Command-line tool for Open Orion PLM"""
    

@cli.command(name="create")
@click.option("--name", help="The name of the project", required=False)
@click.option("--cad-path", help="The path for a step file (CAD/3D) to be processed with the tool", type=click.Path(), required=False)
@click.option("--remote-url", help="The URL of the remote repository", required=False, default=None)
@click.option("--include-assets", help="Include assets in the project", is_flag=True, default=False)
def create_command(name: str, cad_path: str, remote_url: Optional[str], include_assets: bool):
    """Create a new project"""
    from pathlib import Path
    from orion_cli.services.create_service import CreateService
    from orion_cli.helpers.remote_helper import RemoteHelper
    import shutil

    project_path = Path.cwd()


    name = str(click.prompt("Please enter the project name")).strip()

    full_project_path = project_path / name

    if full_project_path.exists():
        logger.info(f"Project '{name}' already exists at {full_project_path}")
        overwrite = click.confirm("Would you like to overwrite it?", default=False)
        if not overwrite:
            logger.info("Exiting without creating project.")
            return
        # Remove the project directory and its contents
        shutil.rmtree(full_project_path)


    # Prompt the user for inputs if not provided
    if not cad_path:
        cad_path = str(click.prompt("CAD file (*.step, *.stp)", type=click.Path(exists=True))).strip()

    if not remote_url:
        provide_remote_url = click.confirm("Would you like to provide the URL of the remote Git repository?", default=False)
        if not provide_remote_url:
            pass
        else:
            remote_url = click.prompt("Remote Git Repository")

    if remote_url:
        # Check if the remote repository is valid and accessible
        valid_url = RemoteHelper.get_valid_remote_url(remote_url)
        if valid_url is None:
            logger.info("Continuing without a remote Git repository.")
        else:
            logger.info(f"Using remote repository: {valid_url}")
        remote_url = valid_url

    # Create the project
    service = CreateService()
    # try:
    service.create(name, project_path, cad_path, remote_url, include_assets)
    logger.info(f"Project '{name}' has been created/updated at {project_path / name}")
    logger.info(f"Original CAD file: {cad_path}")
    logger.info(f"CAD file has been copied in the project directory.")
    logger.info("Project configuration has been created and saved.")
    # except Exception as e:
    #     logger.info(f"Error creating/updating project: {e}")
    #     return

    logger.info("Project creation/update completed successfully.")

@cli.command(name="revision")
@click.option("--project_path", type=click.Path(exists=True),help="The path of the project to be revised", required=False)
@click.option("--cad_path", type=click.Path(exists=True), help="The path for a step file (CAD/3D) to be processed with the tool", required=False)
def revision_command(project_path: Union[str, Path], cad_path: str):
    """Update the project structure and commit the changes"""
    from orion_cli.services.revision_service import RevisionService
    from pathlib import Path
    from orion_cli.helpers.config_helper import ConfigHelper

    project_path = Path.cwd() if not project_path else Path(project_path)
    config_path = project_path / "config.yaml"
    if not config_path.exists():
        click.echo("No config.yaml found in the project directory.")
        click.echo("You can create a project using 'orion create' or provide a valid project path.")
        return

    # Load the configuration
    config = ConfigHelper.load_config(config_path)

    # Use the cad_path from the config if not provided as an argument
    if not cad_path:
        if not config.cad_path or not Path(config.cad_path).is_file():
            click.echo("Invalid CAD path provided in config.")
            return
        cad_path = config.cad_path
        

    service = RevisionService()
    service.revision(project_path, cad_path, config.options)

@cli.command(name="display")
@click.option("--project-path", type=click.Path(exists=True),help="The path of the project to be revised", required=False)
def display_command(project_path: Union[str, Path]):
    """Display the CAD file as three.js html file"""
    from orion_cli.services.revision_service import RevisionService
    from pathlib import Path
    from orion_cli.helpers.config_helper import ConfigHelper

    project_path = Path.cwd() if not project_path else Path(project_path)
    config_path = project_path / "config.yaml"
    if not config_path.exists():
        click.echo("No config.yaml found in the project directory.")
        click.echo("You can create a project using 'orion create' or provide a valid project path.")
        return

    service = DisplayService()
    service.display(project_path)


@cli.command(name="deploy")
@click.option("--deploy-msg",help="Project deployment message",required=False)
def deploy_command(deploy_msg: Optional[str|None] = None):
    """Deploy the project to the remote repository"""
    from orion_cli.services.deploy_service import DeployService
    from orion_cli.helpers.config_helper import ConfigHelper
    from pathlib import Path
    from orion_cli.helpers.remote_helper import RemoteHelper
    import subprocess

    """Deploy the project to the remote repository"""
    project_path = Path.cwd()
    config_path = project_path / "config.yaml"

    if not config_path.exists():
        click.echo("No config.yaml found in the project directory.")
        click.echo("You can create a project using 'orion create' or provide a valid project path.")
        return

    # Load the configuration
    config = ConfigHelper.load_config(config_path)
    if not config.repo_url:
        click.echo("No remote repository URL found in the project config.yaml.")
        click.echo("Please update the config.yaml file with the remote repository URL.")
        return

    # 1 & 2. Check and update remote URL if necessary
    try:
        current_remote = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            universal_newlines=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        current_remote = None

    if current_remote != config.repo_url:
        click.echo(f"Updating the remote URL to {config.repo_url}...")
        try:
            if current_remote:
                subprocess.check_call(["git", "remote", "set-url", "origin", config.repo_url])
            else:
                subprocess.check_call(["git", "remote", "add", "origin", config.repo_url])
        except subprocess.CalledProcessError:
            click.echo("Failed to update the remote URL. Please check your config.yaml and try again.")
            return

    # 3. Validate the remote URL
    if not RemoteHelper.validate_remote_url(config.repo_url):
        click.echo("The remote URL in config.yaml is not valid or not accessible.")
        click.echo("Please update your config.yaml with a valid remote URL and try again.")
        return

    # 4. Set up tracking for the current branch
    try:
        current_branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            universal_newlines=True
        ).strip()

        # Check if the remote branch exists
        remote_branches = subprocess.check_output(
            ["git", "ls-remote", "--heads", "origin", current_branch],
            universal_newlines=True
        ).strip()

        if remote_branches:
            # Remote branch exists, set up tracking
            subprocess.check_call([
                "git", "branch", "--set-upstream-to", f"origin/{current_branch}", current_branch
            ])
            click.echo(f"Tracking set up for branch '{current_branch}' with 'origin/{current_branch}'")
        else:
            # Remote branch doesn't exist, prepare to push
            click.echo(f"Remote branch 'origin/{current_branch}' doesn't exist. It will be created on first push.")

        click.echo("Remote URL validated and branch tracking configured successfully.")
    except subprocess.CalledProcessError as e:
        click.echo(f"An error occurred while setting up branch tracking: {e}")
        click.echo("Continuing with deployment, but you may need to push with '-u' flag on first push.")

    
    if not deploy_msg:
        deploy_msg = click.prompt("Please enter a deployment message")
    
    # Proceed with deployment
    service = DeployService()
    service.deploy(deploy_msg or "")


if __name__ == "__main__":
    cli()
