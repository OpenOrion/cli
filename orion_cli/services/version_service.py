from pathlib import Path
import subprocess
from typing import Optional, Union
from orion_cli.models.archive import ArchiveConfig
from orion_cli.utils.logging import logger
from orion_cli.services.archive_service import ArchiveService
from orion_cli.helpers.remote_helper import VersionHelper


class VersionService:
    @staticmethod
    def initialize_archive(
        name: str,
        path: Union[str, Path],
        cad_path: Union[str, Path],
        remote_url: Optional[str] = None,
        include_assets: bool = False,
        author_name: Optional[str] = None,
        author_email: Optional[str] = None,
    ):
        """Create a new archive"""
        VersionHelper.assert_git_configured()

        archive_path = Path(path) / name
        cad_path = Path(cad_path).resolve()

        # Create and save archive config
        archive_config = ArchiveConfig(
            name=name,
            cad_path=cad_path.name,
            repo_url=remote_url,
            include_assets=include_assets,
        )

        # Create the archive using CadService
        cad_archive = ArchiveService.create_archive(
            archive_path=archive_path,
            cad_file=cad_path,
            config=archive_config,
            verbose=True,
        )
        VersionHelper.initialize_repo(archive_path, author_name, author_email)

        return cad_archive

    @staticmethod
    def revise_repo(
        archive_path: Union[str, Path],
        cad_path: Union[str, Path],
        config: Optional[ArchiveConfig] = None,
    ):
        """Update the archive structure and commit the changes"""
        VersionHelper.assert_git_configured()

        archive_path = Path(archive_path)
        cad_path = Path(cad_path).resolve()

        try:
            logger.info(f"Revising archive at {archive_path} with CAD file {cad_path}")
            # Regenerate the archive structure
            ArchiveService.revise_archive(
                archive_path,
                cad_path,
                write=True,
                config=config,
                verbose=True,
            )

            # Show changes before staging
            VersionHelper.show_changes(archive_path)

            subprocess.run(["git", "add", "."], cwd=archive_path, check=True)
            logger.info("Changes staged.")

        except Exception as e:
            error_message = f"Error occurred while executing the revision: {e}"
            logger.info(error_message)
            logger.exception(error_message)

    @staticmethod
    def deploy_repo():
        """Deploy the archive to a remote repository"""
        VersionHelper.assert_git_configured()

        try:
            VersionHelper.push()
        except Exception as e:
            error_message = f"Error occurred while deploying the archive: {e}"
            logger.info(error_message)
            logger.exception(error_message)
