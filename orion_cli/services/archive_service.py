import yaml
import logging
from pathlib import Path
from typing import Optional, Union
import shutil
from orion_cli.helpers.archive_helper import ArchiveHelper
from orion_cli.helpers.asset_helper import AssetHelper, SVGOptions
from orion_cli.helpers.cad_helper import CadHelper
from orion_cli.models.archive import (
    ArchiveConfig,
    AssemblyIndex,
    CadArchive,
    CatalogItem,
    Inventory,
    InventoryCatalog,
    Assembly
)
from orion_cli.templates.README_template import README_TEMPLATE
from orion_cli.templates.gitignore_template import GITIGNORE_TEMPLATE
from orion_cli.utils.logging import logger


INVENTORY_DIRECTORY = "inventory"
PARTS_DIRECTORY = "inventory/parts"
ASSEMBLY_DIRECTORY = "assemblies"
ASSETS_DIRECTORY = "assets"


class ArchiveService:
    @staticmethod
    def write_inventory(
        archive_path: Union[Path, str], inventory: Inventory, verbose=False
    ):
        logger.setLevel(logging.INFO if verbose else logging.ERROR)

        archive_path = Path(archive_path)
        inventory_path = archive_path / INVENTORY_DIRECTORY
        parts_path = archive_path / PARTS_DIRECTORY

        logger.info(f"Writing inventory to {inventory_path}")

        if archive_path.is_dir() and inventory_path.is_dir():
            shutil.rmtree(inventory_path)
        inventory_path.mkdir(parents=True, exist_ok=True)
        parts_path.mkdir(parents=True, exist_ok=True)

        # Generate BREP files for each part
        for checksum, part in inventory.parts.items():
            part_name = inventory.catalog.items[checksum].name
            brep_path = parts_path / f"{part_name}.brep"
            with open(brep_path, "w") as f:
                CadHelper.export_brep(part.wrapped, f"{brep_path}")
                logger.info(f"- Exported part '{part_name}'")

        with open(inventory_path / "catalog.json", "w") as f:
            f.write(inventory.catalog.model_dump_json(indent=4))

    @staticmethod
    def write_assets(
        archive_path: Union[Path, str],
        archive: CadArchive,
        index: Optional[AssemblyIndex] = None,
        verbose=False,
    ):
        logger.setLevel(logging.INFO if verbose else logging.ERROR)

        archive_path = Path(archive_path)
        assets_path = archive_path / ASSETS_DIRECTORY
        inventory_path = archive_path / INVENTORY_DIRECTORY
        assets_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Writing assets to {archive_path}")

        part_names = set()
        part_svg_options = SVGOptions(showAxes=False, marginLeft=20)
        # Iterate catalog items for assets
        for checksum, catalog_item in archive.inventory.catalog.items.items():
            part = archive.inventory.parts[checksum]
            part_names.add(catalog_item.name)

            # Generate SVGs for each part if they are modified or don't exist
            svg_path = assets_path / f"{catalog_item.name}.svg"
            if (
                not index
                or index
                and checksum in index.is_part_modified
                or not svg_path.exists()
            ):
                logger.info(f"- Generating SVG for part '{catalog_item.name}'")
                svg = AssetHelper.getSVG(part, part_svg_options)
                # svg = getSVG(part, part_svg_options)

                with open(svg_path, "w") as f:
                    f.write(svg)

        # Generate assets for main assembly
        with open(inventory_path / "README.md", "w") as f:
            inventory_md = AssetHelper.get_inventory_markdown(
                archive.inventory, assets_path
            )
            f.write(inventory_md)

        # Generate SVG for root assembly
        main_assembly_svg_path = assets_path / f"{archive.root_assembly.long_name}.svg"
        root_asm_modified = (
            index and archive.root_assembly.id in index.is_assembly_modified
        )
        if not index or root_asm_modified or not main_assembly_svg_path.exists():
            logger.info(
                f"- Generating SVG for root assembly '{archive.root_assembly.name}', this may take a sec ..."
            )
            root_assembly_cq = archive.root_assembly.to_cq(archive)
            assembly_svg_options = SVGOptions(
                showAxes=False, marginLeft=20, showHidden=False, strokeWidth=-0.9
            )
            root_assembly_svg = AssetHelper.getSVG(
                root_assembly_cq, assembly_svg_options
            )

            with open(main_assembly_svg_path, "w") as f:
                f.write(root_assembly_svg)

        logger.info("\n\n- Removing SVG files not in inventory")
        for svg_path in assets_path.glob("*.svg"):
            if svg_path.stem not in part_names and svg_path != main_assembly_svg_path:
                svg_path.unlink()

        # Write the content to the new archive's .gitignore file
        (archive_path / ".gitignore").write_text(GITIGNORE_TEMPLATE)

        # Create a README file
        readme_path = archive_path / "README.md"
        if not readme_path.exists():
            readme_content = README_TEMPLATE(
                archive.config.name, archive.config.repo_url, main_assembly_svg_path
            )
            readme_path.write_text(readme_content)

    @staticmethod
    def write_assemblies(
        archive_path: Union[Path, str], archive: CadArchive, verbose=False
    ):
        logger.setLevel(logging.INFO if verbose else logging.ERROR)

        archive_path = Path(archive_path)
        assembly_path = archive_path / ASSEMBLY_DIRECTORY

        logger.info(f"Writing assemblies to {assembly_path}")

        # delete directory path
        if archive_path.is_dir() and assembly_path.is_dir():
            shutil.rmtree(assembly_path)
        assembly_path.mkdir(parents=True, exist_ok=True)

        # Generate assembly files
        for assembly in archive.assemblies.values():
            subassembly_path = assembly_path / assembly.path.lstrip("/")
            subassembly_path.mkdir(parents=True, exist_ok=True)
            with open(subassembly_path / "assembly.json", "w") as f:
                f.write(assembly.model_dump_json(indent=4))

    # TODO: start breaking the function into smaller parts
    @staticmethod
    def write_archive(
        archive_path: Union[Path, str],
        archive: CadArchive,
        index: Optional[AssemblyIndex] = None,
        verbose=False,
    ):
        logger.setLevel(logging.INFO if verbose else logging.ERROR)

        logger.info(f"\n\nWriting archive to {archive_path}")
        archive_path = Path(archive_path)
        archive_path.mkdir(parents=True, exist_ok=True)

        # Write inventory
        logger.info(f"\n\n")
        ArchiveService.write_inventory(archive_path, archive.inventory, verbose)

        # Write assemblies
        logger.info(f"\n\n")
        ArchiveService.write_assemblies(archive_path, archive, verbose)

        # Write assets
        if archive.config.include_assets:
            logger.info(f"\n\n")
            ArchiveService.write_assets(archive_path, archive, index, verbose)

        # Write config
        config_path = archive_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(archive.config.model_dump(), f, default_flow_style=False)

        logger.info(f"Configuration file created at {config_path}")

    @staticmethod
    def create_archive(
        archive_path: Optional[Path] = None,
        cad_path: Optional[Path] = None,
        config: Optional[ArchiveConfig] = None,
        verbose=False,
    ):
        logger.info(f"Creating archive '{config.name}' at {archive_path}")
        archive = CadArchive()

        if config:
            archive.config = config
        if cad_path:
            logger.info(f"\n\nLoading in step file {cad_path}")
            cq_assembly = CadHelper.import_cad(cad_path)
            ArchiveHelper.process_assembly(cq_assembly, archive)
        if archive_path:
            ArchiveService.write_archive(archive_path, archive, verbose=verbose)

        # Copy CAD file to archive directory
        cad_file_name = cad_path.name
        cad_archive_step_file = archive_path / cad_file_name
        shutil.copy2(cad_path, cad_archive_step_file)

        return archive

    @staticmethod
    def revise_archive(
        archive_path: Path,
        cad_path: Path,
        write=False,
        config: Optional[ArchiveConfig] = None,
        verbose=False,
    ):
        logger.setLevel(logging.INFO if verbose else logging.ERROR)
        prev_archive = ArchiveService.read_archive(archive_path)
        cq_assembly = CadHelper.import_step(cad_path)

        revised_archive = CadArchive()
        if config:
            revised_archive.config = config
        index = AssemblyIndex(prev_archive=prev_archive)
        ArchiveService.process_assembly(cq_assembly, revised_archive, index)

        if write:
            ArchiveService.write_archive(
                archive_path, revised_archive, index, verbose=verbose
            )

        return revised_archive

    @staticmethod
    def read_archive(archive_path: Union[Path, str]):
        archive = CadArchive()

        config_path = archive_path / "config.yaml"
        with open(config_path, "r") as f:
            archive.config = ArchiveConfig.model_validate(yaml.safe_load(f))

        archive_path = Path(archive_path)
        assert archive_path.is_dir(), f"archive directory not found: {archive_path}"
        inventory_path = archive_path / INVENTORY_DIRECTORY
        parts_path = inventory_path / "parts"

        with open(inventory_path / "catalog.json", "r") as f:
            catalog = InventoryCatalog.model_validate_json(f.read())
            for checksum, catalog_item in catalog.items.items():
                catalog_item = CatalogItem.model_validate(catalog_item)
                brep_path = parts_path / f"{catalog_item.name}.brep"
                archive.inventory.parts[checksum] = CadHelper.import_brep(brep_path)
                archive.inventory.catalog.items[checksum] = catalog_item

        assembly_path = archive_path / ASSEMBLY_DIRECTORY

        for assembly_file_path in assembly_path.rglob("assembly.json"):
            if assembly_file_path.is_file():
                with open(assembly_file_path, "r") as f:
                    assembly = Assembly.model_validate_json(f.read())
                    assembly.path = (
                        "/"
                        + assembly_file_path.relative_to(
                            assembly_path
                        ).parent.as_posix()
                    )
                    archive.assemblies[assembly.id] = assembly
                    archive.paths[assembly.path] = assembly
                    for part_ref in assembly.parts:
                        archive.part_refs[part_ref.id] = part_ref
                        part_ref.path = assembly.path + "/" + part_ref.name
                        archive.paths[part_ref.path] = part_ref

        return archive

    @staticmethod
    def visualize_archive(
        archive_path: Union[Path, str],
        remote_viewer=False,
        export_html=True,
        auto_open=True,
        verbose=True,
    ):
        logger.setLevel(logging.INFO if verbose else logging.ERROR)

        archive_path = Path(archive_path)
        archive = ArchiveService.read_archive(archive_path)
        cq_assembly = archive.root_assembly.to_cq(archive)

        orion_cache_path = archive_path / ".orion_cache"
        orion_cache_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Generating visualization")
        viewer = CadHelper.get_viewer(
            cq_assembly, orion_cache_path / "tesselation.cache", remote_viewer
        )

        if viewer and export_html:
            html_path = orion_cache_path / "index.html"
            viewer.export_html(str(html_path))
            logger.info(f"\n\nExported HTML to {html_path}")
            # open html in browser
            if auto_open:
                import webbrowser
                webbrowser.open(f"file://{html_path}")
