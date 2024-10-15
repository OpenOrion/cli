import click
import shutil
import pkg_resources
from pathlib import Path
from typing import Optional
from typing import Optional, Union
from orion_cli.services.log_service import logger
from orion_cli.helpers.remote_helper import RemoteHelper
from orion_cli.services.archive_service import ArchiveService
from orion_cli.services.version_service import VersionService


version = pkg_resources.get_distribution("orion_cli").version

logo = """
  ____      _             _______   ____
 / __ \____(_)__  ___    / ___/ /  /  _/
/ /_/ / __/ / _ \/ _ \  / /__/ /___/ /  
\____/_/ /_/\___/_//_/  \___/____/___/ 
"""

logger.info(logo)


@click.group()
@click.version_option(version=version)
def cli():
    """Command-line tool for Open Orion PLM"""


@cli.command(name="create")
@click.option("--name", help="The name of the project", required=False)
@click.option(
    "--cad-path",
    help="The path for a step file (CAD/3D) to be processed with the tool",
    type=click.Path(),
    required=False,
)
@click.option(
    "--remote-url",
    help="The URL of the remote repository",
    required=False,
    default=None,
)
@click.option(
    "--include-assets",
    help="Include assets in the project",
    is_flag=True,
    default=False,
)
def create_command(
    name: str, cad_path: str, remote_url: Optional[str], include_assets: bool
):
    """Create a new project"""
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
        cad_path = str(
            click.prompt("CAD file (*.step, *.stp)", type=click.Path(exists=True))
        ).strip()

    if not remote_url:
        provide_remote_url = click.confirm(
            "Would you like to provide the URL of the remote Git repository?",
            default=False,
        )
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
    VersionService.create(name, project_path, cad_path, remote_url, include_assets)
    logger.info(f"Project '{name}' has been created/updated at {project_path / name}")
    logger.info(f"Original CAD file: {cad_path}")
    logger.info(f"CAD file has been copied in the project directory.")
    logger.info("Project configuration has been created and saved.")

    logger.info("Project creation/update completed successfully.")


@cli.command(name="revision")
@click.option(
    "--project_path",
    type=click.Path(exists=True),
    help="The path of the project to be revised",
    required=False,
)
@click.option(
    "--cad_path",
    type=click.Path(exists=True),
    help="The path for a step file (CAD/3D) to be processed with the tool",
    required=False,
)
def revision_command(project_path: Union[str, Path], cad_path: str):
    """Update the project structure and commit the changes"""
    project_path = Path.cwd() if not project_path else Path(project_path)
    VersionService.revision(project_path, cad_path)


@cli.command(name="display")
@click.option(
    "--project-path",
    type=click.Path(exists=True),
    help="The path of the project to be revised",
    required=False,
)
def display_command(archive_path: Union[str, Path]):
    """Display the CAD file as three.js html file"""
    archive_path = Path.cwd() if not archive_path else Path(archive_path)
    ArchiveService.visualize_archive(archive_path)


@cli.command(name="deploy")
@click.option("--deploy-msg", help="Project deployment message", required=False)
def deploy_command(deploy_msg: Optional[str | None] = None):
    """Deploy the project to the remote repository"""

    """Deploy the project to the remote repository"""
    if not deploy_msg:
        deploy_msg = click.prompt("Please enter a deployment message")

    # Proceed with deployment
    VersionService.deploy(deploy_msg or "")


if __name__ == "__main__":
    cli()
