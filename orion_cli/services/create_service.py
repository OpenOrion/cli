from pathlib import Path
import subprocess
from typing import Optional, Union
from orion_cli.services.log_service import logger
import shutil
from orion_cli.services.cad_service import CadService, ProjectOptions
from orion_cli.helpers.config_helper import ProjectConfig, ConfigHelper
from orion_cli.helpers.remote_helper import RemoteHelper
from orion_cli.templates.README_template import README_TEMPLATE
from orion_cli.templates.gitignore_template import GITIGNORE_TEMPLATE

class CreateService:
    @staticmethod
    def create(
            name: str, 
            path: Union[str, Path], 
            cad_path: Union[str, Path], 
            remote_url: Optional[str] = None, 
            include_assets: bool = False,
            author_name: Optional[str] = None,
            author_email: Optional[str] = None
        ):
        """Create a new project"""
        assert RemoteHelper.ensure_git_installed(), "Git is not installed. Please install Git and try again."
        assert RemoteHelper.ensure_git_configured(), (
            "Git user information is not configured. "
            "Please set your Git user name and email using the following commands:\n"
            'git config --global user.name "Your Name"\n'
            'git config --global user.email "you@example.com"'
        )
        
        project_path = Path(path) / name
        cad_path = Path(cad_path).resolve()
        project_options = ProjectOptions(include_assets=include_assets)
        
        logger.info(f"Creating project '{name}' at {project_path}")
        project_path.mkdir(parents=True, exist_ok=True)

        # Copy CAD file to project directory
        cad_file_name = cad_path.name
        project_step_file = project_path / cad_file_name
        shutil.copy2(cad_path, project_step_file)

        # Create and save project config
        project_config = ProjectConfig(
            name=name,
            cad_path=cad_file_name,
            repo_url=remote_url,
            options=project_options
        )

        config_path = project_path / "config.yaml"
        ConfigHelper.save_config(config_path, project_config)

        logger.info(f"Project '{name}' has been created at {project_path}")
        logger.info(f"Configuration file created at {config_path}")


        # Read the content of the template .gitignore file
        gitignore_content = GITIGNORE_TEMPLATE

        # Write the content to the new project's .gitignore file
        (project_path / ".gitignore").write_text(gitignore_content)


        # Create the project using CadService
        project = CadService.create_project(
            project_path=project_path,
            cad_file=cad_path,
            project_options=project_options,
            verbose=True
        )

        # Create a README file
        cover_image_path = f"./assets/{project.root_assembly.long_name}.svg" if include_assets else None
        readme_content = README_TEMPLATE(name, remote_url, cover_image_path)
        (project_path / "README.md").write_text(readme_content)


        # Initialize a new Git repository
        subprocess.run(["git", "init", "--initial-branch=main"], cwd=project_path, check=True)
        logger.info("Git repository initialized")
        
        if author_name:
            subprocess.run(["git", "config", "user.name", author_name], cwd=project_path, check=True)
            author_email = author_email or "<>"
            subprocess.run(["git", "config", "user.email", author_email], cwd=project_path, check=True)
            logger.info("Added author information")

        # Make initial commit
        subprocess.run(["git", "add", "."], cwd=project_path, check=True)


