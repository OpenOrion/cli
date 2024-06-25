import click


@click.group()
@click.version_option()
def cli():
    "Command-line tool for Open Orion PLM"


@cli.command(name="create")
def create_command():
    "Create a new project"
    click.echo("Your project has been created")

@cli.command(name="revision")
def revision_command():
    "Create a new revision for a project"
    click.echo("Your project has been revisioned")

@cli.command(name="sync")
def sync_command():
    "Sync two directories"
    click.echo("Your project has been synced")
