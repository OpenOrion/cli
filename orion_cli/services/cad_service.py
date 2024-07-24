from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
from typing import Optional, OrderedDict, Sized, Union, cast
import click
import numpy as np
import cadquery as cq
from pydantic import BaseModel, Field
from scipy.spatial.transform import Rotation as R
import shutil
import cadquery as cq
from orion_cli.helpers.cad_helper import CadHelper
from cadquery.occ_impl.exporters.svg import getSVG
import pandas as pd
from orion_cli.services.log_service import logger

# Parameter Labels
PartSurfaceArea = float
PartNumVertices = int
PartGroup = tuple[PartSurfaceArea, PartNumVertices]
PartChecksum = str
AlignedPartChecksum = str
PartName = str
AssemblyPath = str

class InventoryPartVariation(BaseModel):
    color: Optional[list[float]] = None
    price: Optional[float] = None

class CatalogItem(BaseModel):
    name: str
    variations: list[InventoryPartVariation]

MAIN_ASSEMBLY_NAME = "MAIN_ASM"


class InventoryVariationRef(BaseModel):
    checksum: PartChecksum
    id: int

    def __hash__(self):
        return hash((self.checksum, self.id))

@dataclass
class Inventory:
    """
    Catalog of all parts in the project
    """
    parts: dict[PartChecksum, cq.Solid] = field(default_factory=dict)
    catalog: dict[PartChecksum, CatalogItem] = field(default_factory=dict)

    def get_variation(self, ref: InventoryVariationRef):
        return self.catalog[ref.checksum].variations[ref.id]

    def get_variation_id(self, part_checksum: PartChecksum, part_color: Optional[list[float]] = None):
        variation_id = 0
        if part_checksum in self.catalog:
            for id, variation in enumerate(self.catalog[part_checksum].variations):
                if variation.color == part_color:
                    return id
            else:
                return len(self.catalog[part_checksum].variations)
        return variation_id

class PartRef(BaseModel):
    """
    Reference to a part in the inventory with a specific position and orientation (rotation matrix)
    """
    path: str
    variation: InventoryVariationRef
    position: list[float]
    orientation: list[list[float]]

    @property
    def name(self):
        return self.path.split("/")[-1]


class Assembly(BaseModel):
    """
    Assembly of parts and subassemblies as references
    """
    path: AssemblyPath
    children: list[AssemblyPath] = Field(default_factory=list)
    parts: list[PartRef] = Field(default_factory=list)

    def add_child(self, child: "Assembly"):
        self.children.append(child.path)

    @property
    def name(self):
        return self.path.split("/")[-1]

    def to_cq(self, project: "Project"):
        cq_assembly = cq.Assembly(name=self.name)
        for subassembly_path in self.children:
            subassembly = project.assemblies[subassembly_path]
            cq_assembly.add(subassembly.to_cq(project), name=subassembly.name)
        for part_ref in self.parts:
            part = project.inventory.parts[part_ref.variation.checksum]
            loc = CadHelper.get_location(part_ref.orientation, part_ref.position)
            part_variation = project.inventory.get_variation(part_ref.variation)

            # TODO: find a better solution to handle negative rotation determinants (mirrors)
            if loc.wrapped.Transformation().IsNegative():
                aligned_part = CadHelper.transform_solid(part, part_ref.orientation,part_ref.position)
                cq_assembly.add(aligned_part, color=cq.Color(*part_variation.color), name=part_ref.name)
            else:
                cq_assembly.add(
                    part, color=cq.Color(*part_variation.color), name=part_ref.name, loc=loc
                )

        return cq_assembly

class ProjectOptions(BaseModel):
    max_name_depth: int = 3
    normalize_axis: bool = False
    use_references: bool = True
    include_assets: bool = False

@dataclass
class Project:
    assemblies: OrderedDict[AssemblyPath, Assembly] = field(default_factory=OrderedDict)
    part_refs: OrderedDict[AssemblyPath, PartRef] = field(default_factory=OrderedDict)
    inventory: Inventory = field(default_factory=Inventory)
    options: ProjectOptions = field(default_factory=ProjectOptions)
    
    @property
    def root_assembly(self):
        return next(iter(self.assemblies.values()))


@dataclass
class AssemblyIndex:
    """
    Index is for caching operations and revisioning for changes to the assembly
    """
    # caching
    base_parts: dict[PartGroup, cq.Solid] = field(default_factory=dict)
    aligned_refs: dict[AlignedPartChecksum, PartRef] = field(default_factory=dict)
    part_names: dict[PartName, Optional[PartRef]] = field(default_factory=dict)
    part_colors: dict[PartChecksum, set[tuple[float]]] = field(default_factory=dict)

    # revisioning    
    prev_project: Optional["Project"] = None
    is_part_modified: set[InventoryVariationRef] = field(default_factory=set)
    is_assembly_modified: set[AssemblyPath] = field(default_factory=set)


class CadService:
    @staticmethod
    def read_cqassembly(
        cq_assembly: cq.Assembly,
        project: Project,
        index: Optional[AssemblyIndex] = None,
        use_references: bool = True,
        generate_svg: bool = True,
        curr_path: str = "",
    ):
        if index is None:
            index = AssemblyIndex()
        if curr_path == "":
            index.is_assembly_modified.clear()
            index.is_part_modified.clear()

        root_assembly = Assembly(path=curr_path + f"/{cq_assembly.name}")
        assemblies = [root_assembly]
        project.assemblies[root_assembly.path] = root_assembly

        is_modified = False
        for cq_subassembly in cq_assembly.children:
            if isinstance(cq_subassembly, cq.Assembly) and len(cq_subassembly.children):
                subassemblies, is_sub_modified = CadService.read_cqassembly(
                    cq_subassembly,
                    project,
                    index,
                    use_references,
                    generate_svg,
                    root_assembly.path,
                )
                root_assembly.add_child(subassemblies[0])
                assemblies.extend(subassemblies)
                is_modified = is_modified or is_sub_modified
                if is_modified:
                    index.is_assembly_modified.add(root_assembly.path)
            else:
                base_part, part_ref = CadService.get_part(
                    cq_subassembly, root_assembly.path, project.inventory, index, project.options
                )

                is_modified = not(
                    # has the path been previously indexed
                    index.prev_project and part_ref.path in index.prev_project.part_refs and 
                    # if the part checksum is the same
                    index.prev_project.part_refs[part_ref.path].variation == part_ref.variation
                )
                
                if is_modified:
                    index.is_part_modified.add(part_ref.variation)
                    index.is_assembly_modified.add(part_ref.path)

                root_assembly.parts.append(part_ref)
                project.part_refs[part_ref.path] = part_ref

                if part_ref.variation.checksum not in project.inventory.parts:
                    project.inventory.parts[part_ref.variation.checksum] = base_part
                
                part_color =list(cq_subassembly.color.toTuple()) if cq_subassembly.color else None
                variation = InventoryPartVariation(color=part_color)

                if part_ref.variation.checksum not in project.inventory.catalog:
                    project.inventory.catalog[part_ref.variation.checksum] = CatalogItem(name=part_ref.name, variations=[variation])
                elif part_ref.variation.id >= len(project.inventory.catalog[part_ref.variation.checksum].variations):
                    project.inventory.catalog[part_ref.variation.checksum].variations.append(variation)

                CadService.assign_unique_part_names(part_ref, project, index)


        return assemblies, is_modified

    # TODO: Clean this up more
    @staticmethod
    def assign_unique_part_names(part_ref: PartRef, project: Project, index: "AssemblyIndex"):
        part_name = part_ref.name
        assert part_name != MAIN_ASSEMBLY_NAME, f"part name {part_name} is reserved for main assembly"
        # check if part name already exists
        if part_name in index.part_names:
            prev_part_ref = index.part_names[part_name]
            if prev_part_ref and part_ref.variation != prev_part_ref.variation:
                # going back and modifying the previous part name
                prev_path_strs = prev_part_ref.path.split("/")
                prev_part_name = '-'.join(prev_path_strs[min(project.options.max_name_depth, len(prev_path_strs)):])
                assert prev_part_name not in index.part_names, f"part name {prev_part_name} already exists"
                project.inventory.catalog[prev_part_ref.variation.checksum].name = prev_part_name

                # modifying the current part name
                path_strs = part_ref.path.split("/")
                part_name = '-'.join(path_strs[min(project.options.max_name_depth, len(path_strs)):])
                assert part_name not in index.part_names, f"part name {part_name} already exists"
                project.inventory.catalog[part_ref.variation.checksum].name = part_name

        else:
            # add part name to index with part_ref it pertains to
            index.part_names[part_name] = part_ref
            project.inventory.catalog[part_ref.variation.checksum].name = part_name


    @staticmethod
    def get_part(
        cq_subassembly: cq.Assembly,
        assembly_path: str,
        inventory: Optional[Inventory] = None,
        index: Optional[AssemblyIndex] = None,
        options: Optional[ProjectOptions] = None,
    ):
        is_reference = (options and options.use_references) and cq_subassembly.metadata.get(
            "is_reference", False
        )
        if is_reference:
            return CadService.get_referenced_part(cq_subassembly, assembly_path, inventory)
        else:
            normalize_axis=options is not None and options.normalize_axis
            return CadService.get_non_reference_part(cq_subassembly, assembly_path, inventory, index, normalize_axis)

    @staticmethod
    def get_referenced_part(cq_subassembly: cq.Assembly, assembly_path: str, inventory: Optional[Inventory] = None):
        base_part = cast(cq.Solid, cast(cq.Workplane, cq_subassembly.obj).val())
        translation, euler_angles = cq_subassembly.loc.toTuple()
        rotmat = R.from_euler("xyz", euler_angles, degrees=True).as_matrix()
        part_checksum = CadHelper.get_part_checksum(base_part)
        
        part_color =list(cq_subassembly.color.toTuple()) if cq_subassembly.color else None
        variation_id = 0 if inventory is None else inventory.get_variation_id(part_checksum, part_color)

        part_ref = PartRef(
            path=f"{assembly_path}/{cq_subassembly.name}",
            variation=InventoryVariationRef(
                checksum=part_checksum, 
                id=variation_id
            ),
            position=list(translation),
            orientation=rotmat.tolist(),
        )
        return base_part, part_ref

    @staticmethod
    def get_non_reference_part(
        cq_subassembly: cq.Assembly, 
        assembly_path: str, 
        inventory: Optional[Inventory] = None, 
        index: Optional[AssemblyIndex] = None, 
        normalize_axis: bool = False
    ):
        if index is None:
            index = AssemblyIndex()
        aligned_part = cast(cq.Solid, cast(cq.Workplane, cq_subassembly.obj).val()).located(cq_subassembly.loc)

        # check if part has been aligned before
        if normalize_axis:
            aligned_checksum = CadHelper.get_part_checksum(aligned_part)
            if index.prev_project and aligned_checksum in index.aligned_refs:
                part_ref = index.aligned_refs[aligned_checksum]
                base_part = index.prev_project.inventory.parts[part_ref.variation.checksum]
                return base_part, part_ref
        else:
            # if not normalizing axis, then no need to check for aligned part, everything is already fast enough
            aligned_checksum = None

        # otherwise align part and normalize
        part_group = (
            np.round(aligned_part.Area(), 3),
            len(cast(Sized, aligned_part._entities("Vertex"))),
        )
        normalized_part, offset, rotmat = CadHelper.normalize_part(aligned_part, normalize_axis)
        
        # check if part has been normalized before
        if part_group not in index.base_parts:
            base_part = normalized_part
            index.base_parts[part_group] = normalized_part
        else:
            # align part with previously normalized part (in case of symetric inertial axis)
            base_part = index.base_parts[part_group]
            rot_mat_adjustment = CadHelper.align_parts(base_part, normalized_part)
            rotmat = rotmat.dot(rot_mat_adjustment)
                    
        part_checksum = CadHelper.get_part_checksum(base_part)

        # recreated_original_solid = CadHelper.transform_solid(index.base_parts[part_group], rotmat).translate(offset.tolist())
        # recreated_original_solid_checksum = CadHelper.get_part_checksum(recreated_original_solid)
        # original_solid_checksum = CadHelper.get_part_checksum(aligned_part)
        # assert recreated_original_solid_checksum == original_solid_checksum, f"recreated_original_solid_checksum: {recreated_original_solid_checksum} != original_solid_checksum: {original_solid_checksum}"

        part_color =list(cq_subassembly.color.toTuple()) if cq_subassembly.color else None
        variation_id = 0 if inventory is None else inventory.get_variation_id(part_checksum, part_color)

        part_ref = PartRef(
            path=f"{assembly_path}/{cq_subassembly.name}",
            variation=InventoryVariationRef(
                checksum=part_checksum, 
                id=variation_id
            ),
            position=offset.tolist(),
            orientation=rotmat.tolist(),
        )

        # cache aligned part
        if aligned_checksum:
            index.aligned_refs[aligned_checksum] = part_ref

        return base_part, part_ref

    @staticmethod
    def inventory_markdown(inventory: Inventory, assets_path: Path):
        md = "# Inventory\n"

        data = []
        for item in inventory.catalog.values():
          svg_path = assets_path / f"{item.name}.svg"
          data_item = {"": f"![{svg_path}](../{svg_path})", "Name": item.name}
          data.append(data_item)

        # Create a DataFrame
        df = pd.DataFrame(data)


        return md + df.to_markdown(index=False)

    @staticmethod
    def write_project(project_path: Union[Path, str], project: Project, index: Optional[AssemblyIndex] = None, verbose=False):
        logger.setLevel(logging.INFO if verbose else logging.ERROR)

        logger.info(f"\n\nWriting project to {project_path}")

        project_path = Path(project_path)
        project_path.mkdir(parents=True, exist_ok=True)
        assembly_path = project_path / "assemblies"
        assets_path = project_path / "assets"
        inventory_path = project_path / "inventory"


        # delete directory path
        if project_path.is_dir():
            if assembly_path.is_dir():
                shutil.rmtree(assembly_path)
            if inventory_path.is_dir():
                shutil.rmtree(inventory_path)
        inventory_path.mkdir(parents=True, exist_ok=True)
        assembly_path.mkdir(parents=True, exist_ok=True)
        assets_path.mkdir(parents=True, exist_ok=True)

        # Generate BREP files for each part
        part_names = set()
        logger.info(f"\n\nWriting inventory to {inventory_path}")
        for checksum, part in project.inventory.parts.items():
            part_name = project.inventory.catalog[checksum].name
            part_names.add(part_name)

            brep_path = inventory_path / f"{part_name}.brep"
            with open(brep_path, "w") as f:
                CadHelper.export_brep(part.wrapped, f"{brep_path}")
                logger.info(f"- Exported part '{part_name}'")

            # Generate SVGs for each part if they are modified or don't exist
            if project.options.include_assets:
                svg_path = assets_path / f"{part_name}.svg"
                if not index or index and checksum in index.is_part_modified or not svg_path.exists():
                    logger.info(f"- Generating SVG for part '{part_name}'")
                    svg = getSVG(part, {"showAxes": False, "marginLeft": 20})
                    with open(svg_path, "w") as f:
                        f.write(svg)

        if project.options.include_assets:
            logger.info("- Generating SVG for main assembly, this might take a sec ...")
            if index is None or project.root_assembly.path in index.is_assembly_modified:
                cq_assembly = project.root_assembly.to_cq(project)
                cq_comp = cq_assembly.toCompound()
                svg = getSVG(cq_comp, {"showAxes": False, "marginLeft": 20})
                with open(assets_path / f"{MAIN_ASSEMBLY_NAME}.svg", "w") as f:
                    f.write(svg)

            logger.info("- Removing SVG files not in inventory")
            for svg_path in assets_path.glob("*.svg"):
                if svg_path.stem not in part_names and svg_path.stem != MAIN_ASSEMBLY_NAME:
                    svg_path.unlink()


        with open(inventory_path / "README.md", "w") as f:
            f.write(CadService.inventory_markdown(project.inventory, assets_path.relative_to(project_path)))

        with open(inventory_path / "catalog.json", "w") as f:
            serialized_items = {key: model.model_dump() for key, model in project.inventory.catalog.items()}

            json.dump(serialized_items, f, indent=4)

        # Generate assembly files
        logger.info(f"\n\nWriting assemblies to {assembly_path}")
        for assembly in project.assemblies.values():
            subassembly_path = assembly_path / assembly.path.lstrip("/")
            subassembly_path.mkdir(parents=True, exist_ok=True)
            with open(subassembly_path / "assembly.json", "w") as f:
                f.write(assembly.model_dump_json(indent=4))
    
    @staticmethod
    def create_project(
        project_path: Path,
        cad_file: Optional[Path] = None,
        project_options: Optional[ProjectOptions] = None,
        verbose=False
    ):
        project = Project()
        if project_options:
            project.options = project_options
        if cad_file:
            # Create the new directory
            logger.info(f"\n\nLoading in step file {cad_file}")
            cq_assembly = CadHelper.import_cad(cad_file)
            CadService.read_cqassembly(cq_assembly, project)
        CadService.write_project(project_path, project, verbose=verbose)

    @staticmethod
    def revise_project(project_path: Path, cad_path: Path, write=False, project_options: Optional[ProjectOptions] = None, verbose=False):
        logger.setLevel(logging.INFO if verbose else logging.ERROR)

        prev_project = CadService.read_project(project_path)

        cq_assembly = CadHelper.import_step(cad_path)

        revised_project = Project()
        if project_options:
            revised_project.options = project_options
        index = AssemblyIndex(prev_project=prev_project)
        CadService.read_cqassembly(cq_assembly, revised_project, index)

        if write:
            CadService.write_project(project_path, revised_project, verbose=verbose)
        
        return revised_project

    @staticmethod
    def read_project(project_path: Union[Path, str]):
        project = Project()

        project_path = Path(project_path)
        assert project_path.is_dir(), f"Project directory not found: {project_path}"
        inventory_path = project_path / "inventory"
        with open(inventory_path / "catalog.json", "r") as f:
            catalog = dict(json.load(f))
            for checksum, catalog_item in catalog.items():
                catalog_item = CatalogItem.model_validate(catalog_item)
                brep_path = inventory_path / f"{catalog_item.name}.brep"
                project.inventory.parts[checksum] = cq.Solid(
                    CadHelper.import_brep(brep_path)
                )

        assembly_path = project_path / "assemblies"

        for assembly_file_path in assembly_path.rglob("assembly.json"):
            if assembly_file_path.is_file():
                with open(assembly_file_path, "r") as f:
                    assembly = Assembly.model_validate_json(f.read())
                    project.assemblies[assembly.path] = assembly
                    for part_ref in assembly.parts:
                        project.part_refs[part_ref.path] = part_ref

        return project

    @staticmethod
    def visualize_project(project_path: Union[Path, str], remote_viewer=False, export_html=True, verbose=True):
        logger.setLevel(logging.INFO if verbose else logging.ERROR)

        project_path = Path(project_path)
        project = CadService.read_project(project_path)

        cq_assembly = project.root_assembly.to_cq(project)

        orion_cache_path = project_path / ".orion_cache"
        orion_cache_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Generating visualization")
        viewer = CadHelper.get_viewer(cq_assembly, orion_cache_path / "tesselation.cache", remote_viewer)
        
        if viewer and export_html:
            viewer.export_html(str(orion_cache_path / "index.html"))
            logger.info(f"Exported HTML to {orion_cache_path / 'index.html'}, open in browser to view")
