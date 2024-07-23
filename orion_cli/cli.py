from typing import Optional
import click
import os
from orion_cli.services.log_service import logger
CACHE_FILE_PATH = 'cadquery_run.cache'

@click.group()
@click.version_option()
def cli():
    """Command-line tool for Open Orion PLM"""

@cli.command(name="create")
@click.option("--name", help="The name of the project", required=False)
@click.option("--cad_path", help="The path for a step file (CAD/3D) to be processed with the tool", type=click.Path(), required=False)
@click.option("--remote_url", help="The URL of the remote repository", required=False, default=None)
def create_command(name: str, cad_path: str, remote_url: Optional[str]):
    """Create a new project"""
    from pathlib import Path
    from orion_cli.services.create_service import CreateService
    from orion_cli.helpers.remote_helper import RemoteHelper
    import shutil

    project_path = Path.cwd()


    name = click.prompt("Please enter the project name")

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
        cad_path = click.prompt("CAD file (*.step, *.stp)", type=click.Path(exists=True))

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
    try:
        service.create(name, project_path, cad_path, remote_url)
        logger.info(f"Project '{name}' has been created/updated at {project_path / name}")
        logger.info(f"Original CAD file: {cad_path}")
        logger.info(f"CAD file has been copied in the project directory.")
        logger.info("Project configuration has been created and saved.")
    except Exception as e:
        logger.info(f"Error creating/updating project: {e}")
        return

    logger.info("Project creation/update completed successfully.")

@cli.command(name="config")
def config_command():
    """Configure GitHub credentials"""
    from orion_cli.services.config_service import ConfigService
    service = ConfigService()
    service.config()

@cli.command(name="revision")
@click.option(
    "--project-path", type=click.Path(exists=True), prompt="Please enter the project path",
    help="The path of the project to be revised"
)
@click.option(
    "--step-file", type=click.Path(exists=True), prompt="Please enter the step file path",
    help="The path for a step file (CAD/3D) to be processed with the tool"
)
@click.option(
    "--commit-message", default="Updated project structure", prompt="Please enter the commit message",
    help="The commit message for the revision"
)
def revision_command(project_path: str, cad_path: str, commit_message: str):
    """Update the project structure and commit the changes"""
    from orion_cli.services.revision_service import RevisionService
    service = RevisionService()
    service.revision(project_path, cad_path, commit_message)

@cli.command(name="sync")
@click.option(
    "--project-path", type=click.Path(exists=True), prompt="Please enter the project path",
    help="The path of the project to be synchronized"
)
def sync_command(project_path: str):
    """Sync the project with the remote repository"""
    from orion_cli.services.sync_service import SyncService
    service = SyncService()
    service.sync(project_path)

@cli.command(name="test_cadquery")
def test_cadquery_command():
    """Test CadQuery by creating and displaying a basic shape"""
    if not os.path.exists(CACHE_FILE_PATH):
        logger.info("This may take a while the first time it is run. Please be patient...")
        with open(CACHE_FILE_PATH, 'w') as f:
            f.write("")  # Create the cache file

    import cadquery as cq
    from cadquery import exporters

    # Create a simple box shape
    box = cq.Workplane("front").box(1, 2, 3)

    # Export the shape to an STL file
    exporters.export(box, 'test_shape.stl')

    logger.info("CadQuery test shape created and saved as 'test_shape.stl'")

if __name__ == "__main__":
    cli()
