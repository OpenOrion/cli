import subprocess
import click
from typing import Optional


class RemoteHelper:
    @staticmethod
    def validate_remote_url(remote_url: str) -> bool:
        try:
            subprocess.check_output(["git", "ls-remote", remote_url], stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            return False
        
    @classmethod
    def get_valid_remote_url(cls, initial_url: Optional[str] = None) -> Optional[str]:
        remote_url = initial_url
        while True:
            if remote_url is not None:
                if cls.validate_remote_url(remote_url):
                    return remote_url
                else:
                    click.echo("Invalid remote repository or access denied.")
            
            choice = click.prompt(
                "Do you want to (1) enter a new URL, (2) continue without a remote, or (3) abort?",
                type=click.Choice(['1', '2', '3']),
                show_choices=True
            )
            
            if choice == '1':
                remote_url = click.prompt("Please enter a valid remote URL", type=str)
            elif choice == '2':
                return None
            else:  # choice == '3'
                click.echo("Operation aborted.")
                raise click.Abort()