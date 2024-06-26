import click
import subprocess
import os
import requests

def generate(step_file, project_path, project_name):
    # Create directory structure
    parts_path = os.path.join(project_path, "parts")
    assemblies_path = os.path.join(project_path, "assemblies", project_name)
    
    try:
        os.makedirs(parts_path, exist_ok=True)
        os.makedirs(assemblies_path, exist_ok=True)
        
        # Create README.md and assembly.yml in assemblies/project_name
        readme_path = os.path.join(assemblies_path, "README.md")
        assembly_yml_path = os.path.join(assemblies_path, "assembly.yml")
        
        with open(readme_path, 'w') as readme_file:
            readme_file.write(f"# {project_name} Assembly\n")

        with open(assembly_yml_path, 'w') as assembly_yml_file:
            assembly_yml_file.write("assembly:\n  description: Assembly configuration\n")
        
        click.echo(f"Created directory structure under {project_path}")
    except Exception as e:
        click.echo(f"Error creating directory structure: {e}")


@click.group()
@click.version_option()
def cli():
    "Command-line tool for Open Orion PLM"


@cli.command(name="create")
@click.argument('name')
@click.option('--path', default='.', help='The directory where the project will be created')
@click.option('--step-file', type=click.Path(exists=True), help='The path for a step file (CAD/3D) to be processed with the tool')
def create_command(name, path, step_file):
    """Create a new project"""
    project_path = os.path.join(path, name)
    
    try:
        # Create the new directory
        os.makedirs(project_path, exist_ok=True)
        click.echo(f"Project '{name}' has been created at {project_path}")

        # Initialize a new Git repository
        subprocess.run(["git", "init"], cwd=project_path, check=True)
        click.echo("Initialized a new Git repository")

        if step_file:
            generate(step_file, project_path, name)
            click.echo(f"Step file to be processed: {step_file}")
    except Exception as e:
        click.echo(f"Error: {e}")

@cli.command(name="revision")
@click.argument('project-path', type=click.Path(exists=True))
@click.argument('step-file', type=click.Path(exists=True))
@click.option('--commit-message', default='Updated project structure', help='The commit message for the revision')
def revision_command(project_path, step_file, commit_message):
    """Update the project structure and commit the changes"""
    project_name = os.path.basename(project_path)
    
    try:
        # Regenerate the project structure
        generate(step_file, project_path, project_name)

        # Git add and commit
        subprocess.run(["git", "add", "."], cwd=project_path, check=True)
        subprocess.run(["git", "commit", "-m", commit_message], cwd=project_path, check=True)
        click.echo(f"Changes committed with message: {commit_message}")
    except Exception as e:
        click.echo(f"Error: {e}")


def is_git_repo(path):
    return os.path.isdir(os.path.join(path, '.git'))

def get_remote_url(path):
    result = subprocess.run(["git", "config", "--get", "remote.origin.url"], cwd=path, capture_output=True, text=True)
    return result.stdout.strip()

def get_current_branch(path):
    result = subprocess.run(["git", "branch", "--show-current"], cwd=path, capture_output=True, text=True)
    return result.stdout.strip()

def is_remote_ahead(path):
    result = subprocess.run(["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"], cwd=path, capture_output=True, text=True)
    behind, ahead = map(int, result.stdout.split())
    return behind == 0 and ahead > 0

def is_remote_behind(path):
    result = subprocess.run(["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"], cwd=path, capture_output=True, text=True)
    behind, ahead = map(int, result.stdout.split())
    return behind > 0 and ahead == 0

def create_github_repo(repo_name):
    result = subprocess.run(["gh", "repo", "create", repo_name, "--public", "--source=.", "--remote=origin", "--push"], capture_output=True, text=True)
    if result.returncode != 0:
        raise click.ClickException(f"Failed to create GitHub repository: {result.stderr.strip()}")
    return f"git@github.com:your-github-username/{repo_name}.git"

@cli.command(name="sync")
@click.argument('project_path', type=click.Path(exists=True))
def sync_command(project_path):
    """Sync the project with the remote repository"""
    try:
        if not is_git_repo(project_path):
            raise click.ClickException("No .git directory found. Please run `orion create` followed by `orion revision`.")

        remote_url = get_remote_url(project_path)
        current_branch = get_current_branch(project_path)
        project_name = os.path.basename(os.path.abspath(project_path))

        if not remote_url:
            remote_url = create_github_repo(project_name)
            subprocess.run(["git", "remote", "add", "origin", remote_url], cwd=project_path, check=True)
            subprocess.run(["git", "push", "-u", "origin", current_branch], cwd=project_path, check=True)
            click.echo(f"Project pushed to remote repository: {remote_url}")
        else:
            subprocess.run(["git", "fetch"], cwd=project_path, check=True)
            if is_remote_ahead(project_path):
                click.echo("Remote repository is ahead. Pulling changes.")
                subprocess.run(["git", "pull"], cwd=project_path, check=True)
            elif is_remote_behind(project_path):
                click.echo("Local repository is behind. Pushing changes.")
                subprocess.run(["git", "push"], cwd=project_path, check=True)
            else:
                click.echo("Local and remote repositories are in sync.")

    except subprocess.CalledProcessError as e:
        click.echo(f"Error: {e}")
    except click.ClickException as e:
        click.echo(f"Error: {e}")



