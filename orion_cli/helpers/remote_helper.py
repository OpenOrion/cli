import subprocess
import click
from typing import Optional
from orion_cli.utils.logging import logger
import subprocess
from typing import Optional


class RemoteHelper:
    @staticmethod
    def get_remote_url():
        return subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            universal_newlines=True,
            stderr=subprocess.DEVNULL,
        ).strip()

    @staticmethod
    def validate_remote_url(remote_url: str) -> bool:
        try:
            subprocess.check_output(
                ["git", "ls-remote", remote_url], stderr=subprocess.DEVNULL
            )
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def ensure_git_installed() -> bool:
        try:
            subprocess.check_output(["git", "--version"], stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            return False
        except FileNotFoundError:
            return False

    @staticmethod
    def ensure_git_configured() -> bool:
        try:
            user_name = subprocess.check_output(
                ["git", "config", "--global", "user.name"], stderr=subprocess.DEVNULL
            ).strip()
            user_email = subprocess.check_output(
                ["git", "config", "--global", "user.email"], stderr=subprocess.DEVNULL
            ).strip()
            return bool(user_name) and bool(user_email)
        except subprocess.CalledProcessError:
            return False

    @classmethod
    def get_valid_remote_url(cls, initial_url: Optional[str] = None) -> Optional[str]:
        if not cls.ensure_git_installed():
            logger.info(
                "Git is not installed on your machine. Please install Git to continue."
            )
            raise click.Abort()

        remote_url = initial_url
        while True:
            if remote_url is not None:
                if cls.validate_remote_url(remote_url):
                    return remote_url.strip()
                else:
                    logger.info("Invalid remote repository or access denied.")

            choice = click.prompt(
                "Do you want to (1) enter a new URL, (2) continue without a remote, or (3) abort?",
                type=click.Choice(["1", "2", "3"]),
                show_choices=True,
            )

            if choice == "1":
                remote_url = str(
                    click.prompt("Please enter a valid remote URL", type=str)
                ).strip()
            elif choice == "2":
                return None
            else:  # choice == '3'
                logger.info("Operation aborted.")
                raise click.Abort()
