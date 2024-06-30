import os
import click
import configparser

CONFIG_FILE = os.path.expanduser("~/.orion_config")

class ConfigService:
    def config(self):
        """Configure GitHub credentials"""
        username = click.prompt("Please enter your GitHub username")
        token = click.prompt(
            "Please enter your GitHub personal access token", hide_input=True
        )

        config = configparser.ConfigParser()
        config["GitHub"] = {"username": username, "token": token}

        with open(CONFIG_FILE, "w") as configfile:
            config.write(configfile)

        click.echo(f"GitHub credentials saved to {CONFIG_FILE}")
