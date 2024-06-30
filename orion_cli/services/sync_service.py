import os
import subprocess
import click
import configparser
from github import Github, GithubException

CONFIG_FILE = os.path.expanduser("~/.orion_config")


class SyncService:
    def is_git_repo(self, path):
        return os.path.isdir(os.path.join(path, ".git"))

    def get_remote_url(self, path):
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=path,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def get_current_branch(self, path):
        result = subprocess.run(
            ["git", "branch", "--show-current"], cwd=path, capture_output=True, text=True
        )
        return result.stdout.strip()

    def is_remote_ahead(self, path):
        result = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"],
            cwd=path,
            capture_output=True,
            text=True,
        )
        if not result.stdout.strip():
            return False  # No commits to compare
        behind, ahead = map(int, result.stdout.split())
        return behind == 0 and ahead > 0

    def is_remote_behind(self, path):
        result = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"],
            cwd=path,
            capture_output=True,
            text=True,
        )
        if not result.stdout.strip():
            return False  # No commits to compare
        behind, ahead = map(int, result.stdout.split())
        return behind > 0 and ahead == 0

    def create_github_repo(self, github, repo_name):
        try:
            repo = github.get_user().create_repo(repo_name)
            return repo.ssh_url
        except GithubException as e:
            raise click.ClickException(
                f"Failed to create GitHub repository: {e.data['message']}"
            )

    def load_config(self):
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        if "GitHub" in config:
            return config["GitHub"]["username"], config["GitHub"]["token"]
        else:
            raise click.ClickException(
                "GitHub credentials not configured. Please run `orion config`."
            )

    def verify_ssh_key(self):
        result = subprocess.run(
            ["ssh", "-T", "git@github.com"],
            capture_output=True,
            text=True,
        )
        if "successfully authenticated" not in result.stdout and "successfully authenticated" not in result.stderr:
            raise click.ClickException(
                "SSH key not configured. Please configure your SSH key for GitHub. For more information, visit: https://docs.github.com/en/authentication/connecting-to-github-with-ssh"
            )

    def verify_remote_repo(self, remote_url):
        try:
            subprocess.run(
                ["git", "ls-remote", remote_url],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            raise click.ClickException(
                "Remote repository does not exist or is not accessible. Please check the URL and your permissions."
            )

    def sync(self, project_path):
        """Sync the project with the remote repository"""
        try:
            if not self.is_git_repo(project_path):
                raise click.ClickException(
                    "No .git directory found. Please run `orion create` followed by `orion revision`."
                )

            remote_url = self.get_remote_url(project_path)
            current_branch = self.get_current_branch(project_path)

            if not remote_url:
                click.echo("Would you like to provide an existing remote URL or let the Orion CLI create one for you?")
                choice = click.prompt("Enter 'existing' for existing remote URL or 'create' to create a new remote repository", type=click.Choice(['existing', 'create']), default='existing')

                if choice == 'existing':
                    self.verify_ssh_key()
                    remote_url = click.prompt("Enter the remote repository URL")
                    self.verify_remote_repo(remote_url)
                    subprocess.run(
                        ["git", "remote", "add", "origin", remote_url],
                        cwd=project_path,
                        check=True,
                    )
                    # Push the local repository to the remote
                    subprocess.run(
                        ["git", "push", "-u", "origin", current_branch],
                        cwd=project_path,
                        check=True,
                    )
                else:
                    try:
                        username, token = self.load_config()
                    except click.ClickException as e:
                        click.echo(f"Error: {e}")
                        click.echo("Please run `orion config` to set up your GitHub credentials.")
                        return

                    github = Github(token)
                    project_name = os.path.basename(os.path.abspath(project_path))
                    remote_url = self.create_github_repo(github, project_name)
                    subprocess.run(
                        ["git", "remote", "add", "origin", remote_url],
                        cwd=project_path,
                        check=True,
                    )
                    subprocess.run(
                        ["git", "push", "-u", "origin", current_branch],
                        cwd=project_path,
                        check=True,
                    )
                    click.echo(f"Project pushed to remote repository: {remote_url}")

            else:
                current_branch = self.get_current_branch(project_path)
                commits_ahead = self.is_remote_ahead(project_path)
                commits_behind = self.is_remote_behind(project_path)

                if commits_ahead:
                    click.echo("Remote repository is ahead. Pulling changes.")
                    subprocess.run(["git", "pull"], cwd=project_path, check=True)
                elif commits_behind:
                    click.echo("Local repository is behind. Pushing changes.")
                    subprocess.run(["git", "push"], cwd=project_path, check=True)
                else:
                    click.echo("Local and remote repositories are in sync.")

        except GithubException as e:
            click.echo(f"GitHub API Error: {e.data['message']}")
        except subprocess.CalledProcessError as e:
            click.echo(f"Error: {e}")
        except click.ClickException as e:
            click.echo(f"Error: {e}")