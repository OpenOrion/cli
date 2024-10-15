import click
import shutil
import pkg_resources
from pathlib import Path
from typing import Optional, Union
from orion_cli.services.log_service import logger
from orion_cli.helpers.remote_helper import VersionHelper
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
@click.option("--name", help="The name of the archive", required=False)
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
    help="Include assets in the archive",
    is_flag=True,
    default=False,
)
def create_command(
    name: str, cad_path: str, remote_url: Optional[str], include_assets: bool
):
    """Create a new archive"""
    archive_path = Path.cwd()

    name = str(click.prompt("Please enter the archive name")).strip()

    full_archive_path = archive_path / name
    if full_archive_path.exists():
        click.echo(f"archive '{name}' already exists at {full_archive_path}")
        overwrite = click.confirm("Would you like to overwrite it?", default=False)
        if not overwrite:
            click.echo("Exiting without creating archive.")
            return
        # Remove the archive directory and its contents
        shutil.rmtree(full_archive_path)

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

    # Create the archive
    VersionService.initialize_archive(
        name, archive_path, cad_path, remote_url, include_assets
    )
    click.echo(f"archive '{name}' has been initialized at {archive_path / name}")


@cli.command(name="revision")
@click.option(
    "--archive_path",
    type=click.Path(exists=True),
    help="The path of the archive to be revised",
    required=False,
)
@click.option(
    "--cad_path",
    type=click.Path(exists=True),
    help="The path for a step file (CAD/3D) to be processed with the tool",
    required=False,
)
def revision_command(archive_path: Union[str, Path], cad_path: str):
    """Update the archive structure and commit the changes"""
    archive_path = Path.cwd() if not archive_path else Path(archive_path)
    VersionService.revise_repo(archive_path, cad_path)


@cli.command(name="display")
@click.option(
    "--archive-path",
    type=click.Path(exists=True),
    help="The path of the archive to be revised",
    required=False,
)
def display_command(archive_path: Union[str, Path]):
    """Display the CAD file as three.js html file"""
    archive_path = Path.cwd() if not archive_path else Path(archive_path)
    ArchiveService.visualize_archive(archive_path)


@cli.command(name="deploy")
@click.option("--deploy-msg", help="archive deployment message", required=False)
def deploy_command(deploy_msg: Optional[str | None] = None):
    """Deploy the archive to the remote repository"""

    """Deploy the archive to the remote repository"""
    if not deploy_msg:
        deploy_msg = click.prompt("Please enter a deployment message")

    # Proceed with deployment
    VersionService.deploy(deploy_msg or "")


if __name__ == "__main__":
    cli()
