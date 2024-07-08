import click
import os

class CustomPath(click.Path):
    def convert(self, value, param, ctx):
        value = os.path.expanduser(value)
        return super().convert(value, param, ctx)

@click.group()
@click.version_option()
def cli():
    """Command-line tool for Open Orion PLM"""

@cli.command(name="create")
@click.option(
    "--name", prompt="Please enter the project name",
    help="The name of the project"
)
@click.option(
    "--path", default=".", prompt="Please enter the directory where the project will be created",
    help="The directory where the project will be created", type=CustomPath(exists=True)
)
@click.option(
    "--step-file", type=CustomPath(exists=True), prompt="Please enter the path for a step file (CAD/3D) to be processed with the tool",
    help="The path for a step file (CAD/3D) to be processed with the tool", required=False
)
def create_command(name, path, step_file):
    """Create a new project"""
    from orion_cli.services.create_service import CreateService
    service = CreateService()
    service.create(name, path, step_file)

@cli.command(name="config")
def config_command():
    """Configure GitHub credentials"""
    from orion_cli.services.config_service import ConfigService
    service = ConfigService()
    service.config()

@cli.command(name="revision")
@click.option(
    "--project-path", type=CustomPath(exists=True), prompt="Please enter the project path",
    help="The path of the project to be revised"
)
@click.option(
    "--step-file", type=CustomPath(exists=True), prompt="Please enter the step file path",
    help="The path for a step file (CAD/3D) to be processed with the tool"
)
@click.option(
    "--commit-message", default="Updated project structure", prompt="Please enter the commit message",
    help="The commit message for the revision"
)
def revision_command(project_path, step_file, commit_message):
    """Update the project structure and commit the changes"""
    from orion_cli.services.revision_service import RevisionService
    service = RevisionService()
    service.revision(project_path, step_file, commit_message)

@cli.command(name="sync")
@click.option(
    "--project-path", type=CustomPath(exists=True), prompt="Please enter the project path",
    help="The path of the project to be synchronized"
)
def sync_command(project_path):
    """Sync the project with the remote repository"""
    from orion_cli.services.sync_service import SyncService
    service = SyncService()
    service.sync(project_path)

@cli.command(name="test_cadquery")
def test_cadquery_command():
    """Test CadQuery by creating and displaying a basic shape"""
    import cadquery as cq
    from cadquery import exporters

    # Create a simple box shape
    box = cq.Workplane("front").box(1, 2, 3)

    # Export the shape to an STL file
    exporters.export(box, 'test_shape.stl')

    click.echo("CadQuery test shape created and saved as 'test_shape.stl'")

if __name__ == "__main__":
    cli()
