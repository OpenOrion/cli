from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
from typing import Optional, OrderedDict, Sized, Union, cast
import numpy as np
import cadquery as cq
from pydantic import BaseModel, ConfigDict, Field
from scipy.spatial.transform import Rotation as R
import shutil
import cadquery as cq
from orion_cli.helpers.asset_helper import AssetHelper, SVGOptions
from orion_cli.helpers.cad_helper import CadHelper
import pandas as pd
from orion_cli.helpers.numpy_helper import NdArray
from orion_cli.services.log_service import logger
from OCP.gp import gp_Trsf

# Parameter Labels
PartSurfaceArea = float
PartNumVertices = int
PartGroup = tuple[PartSurfaceArea, PartNumVertices]
PartChecksum = str
AlignedPartChecksum = str
PartName = str
AssemblyPath = str

INVENTORY_DIRECTORY = "inventory"
PARTS_DIRECTORY = "inventory/parts"
ASSEMBLY_DIRECTORY = "assemblies"
ASSETS_DIRECTORY = "assets"

class InvetoryPartVariationMetadata(BaseModel):
    price: Optional[float] = None
    url: Optional[str] = None

class InventoryPartVariation(BaseModel):
    id: int
    references: set[AssemblyPath] = Field(default_factory=set)
    color: Optional[list[float]] = None
    metadata: Optional[InvetoryPartVariationMetadata] = None
    
class CatalogItem(BaseModel):
    name: str
    variations: list[InventoryPartVariation]

class InventoryVariationRef(BaseModel):
    checksum: PartChecksum
    id: int

    def __hash__(self):
        return hash((self.checksum, self.id))

class InventoryCatalog(BaseModel):
    items: dict[PartChecksum, CatalogItem] = {}


@dataclass
class Inventory:
    """
    Catalog of all parts in the project
    """
    parts: dict[PartChecksum, cq.Solid] = field(default_factory=dict)
    catalog: InventoryCatalog = field(default_factory=InventoryCatalog)
    
    def get_variation(self, ref: InventoryVariationRef):
        return self.catalog.items[ref.checksum].variations[ref.id-1]

    def get_variation_from_color(self, part_checksum: PartChecksum, part_color: Optional[list[float]] = None):
        if part_checksum in self.catalog.items:
            for variation in self.catalog.items[part_checksum].variations:
                if variation.color == part_color:
                    return variation

    def find_variation_id(self, part_checksum: PartChecksum, part_color: Optional[list[float]] = None):
        variation = self.get_variation_from_color(part_checksum, part_color)
        if variation:
            return variation.id
        elif part_checksum in self.catalog.items:
            return len(self.catalog.items[part_checksum].variations) + 1
        else:
            return 1
class Location(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    position: NdArray
    orientation: NdArray

    def to_cq(self):
        transformation = gp_Trsf()
        transformation.SetValues(
            self.orientation[0][0],
            self.orientation[0][1],
            self.orientation[0][2],
            self.position[0],
            self.orientation[1][0],
            self.orientation[1][1],
            self.orientation[1][2],
            self.position[1],
            self.orientation[2][0],
            self.orientation[2][1],
            self.orientation[2][2],
            self.position[2],
        )
        return cq.Location(transformation)

    @property
    def is_zero(self):
        return np.all(self.position == 0) and np.all(self.orientation == np.eye(3))

    def transform(self, location: Union["Location", cq.Location, None]):
        if location is None:
            return self.model_copy()
        
        if isinstance(location, cq.Location):
            location = Location.convert(location)

        return Location(
            position=self.position + location.position,
            orientation=self.orientation.dot(location.orientation)
        )

    @staticmethod
    def convert(loc: Union["Location", cq.Location, None]):
        if loc is None:
            return Location(position=np.zeros(3), orientation=np.eye(3))
        if isinstance(loc, Location):
            return loc

        transformation = loc.wrapped.Transformation()
        translation = np.array([transformation.Value(1, 4), transformation.Value(2, 4), transformation.Value(3, 4)])
        rotmat = np.array([
            [transformation.Value(1, 1), transformation.Value(1, 2), transformation.Value(1, 3)],
            [transformation.Value(2, 1), transformation.Value(2, 2), transformation.Value(2, 3)],
            [transformation.Value(3, 1), transformation.Value(3, 2), transformation.Value(3, 3)],
        ])

        return Location(
            position=translation,
            orientation=rotmat
        )


class PartRef(BaseModel):
    """
    Reference to a part in the inventory with a specific position and orientation (rotation matrix)
    """
    path: str
    variation: InventoryVariationRef
    location: Optional[Location] = None

    @property
    def name(self):
        return self.path.split("/")[-1]


class Assembly(BaseModel):
    """
    Assembly of parts and subassemblies as references
    """
    path: AssemblyPath
    location: Optional[Location] = None
    children: list[AssemblyPath] = Field(default_factory=list)
    parts: list[PartRef] = Field(default_factory=list)

    def add_child(self, child: "Assembly"):
        self.children.append(child.path)

    @property
    def long_name(self):
        return self.path.lstrip("/").replace("/", "-")

    @property
    def name(self):
        return self.path.split("/")[-1]

    def to_cq(self, project: "Project", abs_location: Optional[Location] = None):
        cq_assembly = cq.Assembly(name=self.name)
        for subassembly_path in self.children:
            subassembly = project.assemblies[subassembly_path]
            asm_abs_location = Location.convert(subassembly.location).transform(abs_location) 
            cq_assembly.add(subassembly.to_cq(project), loc=asm_abs_location.to_cq(),name=subassembly.name)
        for part_ref in self.parts:
            part = project.inventory.parts[part_ref.variation.checksum]
            cq_loc = part_ref.location and part_ref.location.to_cq()
            part_variation = project.inventory.get_variation(part_ref.variation)

            # TODO: find a better solution to handle negative rotation determinants (mirrors)
            cq_color = cq.Color(*CadHelper.rgba_int_to_float(part_variation.color)) if part_variation.color else None
            if cq_loc and cq_loc.wrapped.Transformation().IsNegative():
                part_abs_location = Location.convert(part_ref.location).transform(abs_location)
                aligned_part = CadHelper.transform_solid(part, part_abs_location.orientation, part_abs_location.position)
                cq_assembly.add(aligned_part, color=cq_color, name=part_ref.name)
            else:
                cq_assembly.add(
                    part, color=cq_color, name=part_ref.name, loc=cq_loc
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
    def read_cq_assembly(
        cq_assembly: cq.Assembly,
        project: Optional[Project] = None,
        index: Optional[AssemblyIndex] = None,
        curr_abs_location: Optional[Location] = None,
        curr_path: str = "",
    ):
        if project is None:
            project = Project()
        if index is None:
            index = AssemblyIndex()
        if curr_path == "":
            index.is_assembly_modified.clear()
            index.is_part_modified.clear()

        rel_location = Location.convert(cq_assembly.loc)
        root_assembly = Assembly(
            path=curr_path + f"/{cq_assembly.name}",
            location=rel_location if not rel_location.is_zero else None,
        )
        abs_location = rel_location.transform(curr_abs_location)

        assemblies = [root_assembly]
        project.assemblies[root_assembly.path] = root_assembly

        is_modified = False
        for cq_subassembly in cq_assembly.children:
            if isinstance(cq_subassembly, cq.Assembly) and len(cq_subassembly.children):
                subassemblies, is_sub_modified = CadService.read_cq_assembly(
                    cq_subassembly,
                    project,
                    index,
                    abs_location,
                    root_assembly.path,
                )
                root_assembly.add_child(subassemblies[0])
                assemblies.extend(subassemblies)
                
                is_modified = is_modified or is_sub_modified
                if is_modified:
                    index.is_assembly_modified.add(root_assembly.path)
            else:
                base_part, part_ref = CadService.get_part(
                    cq_subassembly, root_assembly.path, abs_location, project.inventory, index, project.options
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

                # add part reference to root assembly and project
                root_assembly.parts.append(part_ref)
                project.part_refs[part_ref.path] = part_ref

                # add part to inventory
                if part_ref.variation.checksum not in project.inventory.parts:
                    project.inventory.parts[part_ref.variation.checksum] = base_part
                
                # add part variation to index
                part_checksum = part_ref.variation.checksum

                # derive variation from color
                part_color = list(CadHelper.rgba_float_to_int(cq_subassembly.color.toTuple())) if cq_subassembly.color else None
                existing_variation = project.inventory.get_variation_from_color(part_ref.variation.checksum, part_color)
                
                if part_checksum not in project.inventory.catalog.items:
                    project.inventory.catalog.items[part_checksum] = CatalogItem(name=part_ref.name, variations=[])
                
                # if variation does not exist, create a new one, otherwise add part reference
                if not existing_variation:
                    part_variation = InventoryPartVariation(id=part_ref.variation.id, references={part_ref.path}, color=part_color)
                    project.inventory.catalog.items[part_checksum].variations.append(part_variation)
                else:
                    existing_variation.references.add(part_ref.path)
                    part_variation = existing_variation
                
                # keep the metadata from the previous project
                if index and index.prev_project:
                    prev_variation = index.prev_project.inventory.get_variation_from_color(part_ref.variation.checksum, part_color)
                    if prev_variation and not part_variation.metadata:
                        part_variation.metadata = prev_variation.metadata


                CadService.assign_unique_part_names(part_ref, project, index)


        return assemblies, is_modified


    # TODO: Clean this up more
    @staticmethod
    def assign_unique_part_names(part_ref: PartRef, project: Project, index: "AssemblyIndex"):
        part_name = part_ref.name
        # check if part name already exists
        if part_name in index.part_names:
            prev_part_ref = index.part_names[part_name]
            if prev_part_ref and part_ref.variation != prev_part_ref.variation:
                # going back and modifying the previous part name
                prev_path_strs = prev_part_ref.path.split("/")
                prev_part_name = '-'.join(prev_path_strs[min(project.options.max_name_depth, len(prev_path_strs)):])
                assert prev_part_name not in index.part_names, f"part name {prev_part_name} already exists"
                project.inventory.catalog.items[prev_part_ref.variation.checksum].name = prev_part_name

                # modifying the current part name
                path_strs = part_ref.path.split("/")
                part_name = '-'.join(path_strs[min(project.options.max_name_depth, len(path_strs)):])
                assert part_name not in index.part_names, f"part name {part_name} already exists"
                project.inventory.catalog.items[part_ref.variation.checksum].name = part_name

        else:
            # add part name to index with part_ref it pertains to
            index.part_names[part_name] = part_ref
            project.inventory.catalog.items[part_ref.variation.checksum].name = part_name


    @staticmethod
    def get_part(
        cq_subassembly: cq.Assembly,
        assembly_path: str,
        abs_location: Optional[Location] = None,
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
            return CadService.get_non_reference_part(cq_subassembly, assembly_path, abs_location, inventory, index, normalize_axis)

    @staticmethod
    def get_referenced_part(cq_subassembly: cq.Assembly, assembly_path: str, inventory: Optional[Inventory] = None):
        base_part = cast(cq.Solid, cast(cq.Workplane, cq_subassembly.obj).val())
        part_checksum = CadHelper.get_part_checksum(base_part)
        
        part_color = list(CadHelper.rgba_float_to_int(cq_subassembly.color.toTuple())) if cq_subassembly.color else None
        variation_id = inventory.find_variation_id(part_checksum, part_color) if inventory else 1
        location = Location.convert(cq_subassembly.loc)
        part_ref = PartRef(
            path=f"{assembly_path}/{cq_subassembly.name}",
            variation=InventoryVariationRef(
                checksum=part_checksum, 
                id=variation_id
            ),
            location=location if not location.is_zero else None
        )
        return base_part, part_ref

    @staticmethod
    def get_non_reference_part(
        cq_subassembly: cq.Assembly, 
        assembly_path: str, 
        abs_location: Optional[Location] = None,
        inventory: Optional[Inventory] = None, 
        index: Optional[AssemblyIndex] = None, 
        normalize_axis: bool = False
    ):
        if index is None:
            index = AssemblyIndex()
        
        # TODO: check if this is correct
        part_rel_location = Location.convert(cq_subassembly.loc)
        part_abs_location = part_rel_location.transform(abs_location)
        aligned_part = cast(cq.Solid, cast(cq.Workplane, cq_subassembly.obj).val()).located(part_abs_location.to_cq())

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
        part_color = list(CadHelper.rgba_float_to_int(cq_subassembly.color.toTuple())) if cq_subassembly.color else None
        variation_id = inventory.find_variation_id(part_checksum, part_color) if inventory else 1

        part_ref = PartRef(
            path=f"{assembly_path}/{cq_subassembly.name}",
            variation=InventoryVariationRef(
                checksum=part_checksum, 
                id=variation_id
            ),
            location=Location(
                position=offset,
                orientation=rotmat,
            )
        )

        # assert alignment is correct
        # CadHelper.assert_correctly_aligned(base_part, aligned_part, rotmat, offset)

        # cache aligned part
        if aligned_checksum:
            index.aligned_refs[aligned_checksum] = part_ref

        return base_part, part_ref

    @staticmethod
    def get_inventory_markdown(inventory: Inventory, project_path: Union[str, Path, None] = None):
        md = "# Inventory\n"
        data = []
        for catalog_item in inventory.catalog.items.values():
            svg_path =  None
            if project_path:
                project_path = Path(project_path)
                svg_path = (project_path / f"./assets/{catalog_item.name}.svg").relative_to(project_path)
            for variation in catalog_item.variations:
                color_str = ",".join(map(str, variation.color or [1,1,1]))
                data_item = {
                    "Part": "", 
                    "Name": f"{catalog_item.name}", 
                    "Variation": variation.id, 
                    "Quantity": len(variation.references),
                    "Color": f"<span style='color:rgb({color_str})'>&#9724;</span>", 
                    "Price": f"${variation.metadata.price}" if variation.metadata and variation.metadata.price else  "-",
                    "URL": variation.metadata.url if variation.metadata and variation.metadata.url else "-"
                }
                if svg_path and variation.id == 1:
                    data_item["Part"] = f"![{catalog_item.name}-{variation.id}](../{svg_path})"
                if variation.id > 1:
                    data_item["Name"] = "\n"
                data.append(data_item)

        # Create a DataFrame
        df = pd.DataFrame(data)

        return md + df.to_markdown(index=False)

    @staticmethod
    def write_inventory(project_path: Union[Path, str],inventory: Inventory, verbose=False):
        logger.setLevel(logging.INFO if verbose else logging.ERROR)

        project_path = Path(project_path)
        inventory_path = project_path / INVENTORY_DIRECTORY
        parts_path = project_path / PARTS_DIRECTORY

        logger.info(f"Writing inventory to {inventory_path}")

        if project_path.is_dir() and inventory_path.is_dir():
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
    def write_assets(project_path: Union[Path, str], project: Project, index: Optional[AssemblyIndex] = None, verbose=False):
        logger.setLevel(logging.INFO if verbose else logging.ERROR)


        project_path = Path(project_path)
        assets_path = project_path / ASSETS_DIRECTORY
        inventory_path = project_path / INVENTORY_DIRECTORY
        assets_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Writing assets to {project_path}")

        # Generate SVGs for each part if they are modified or don't exist
        part_names = set()
        part_svg_options = SVGOptions(showAxes=False, marginLeft=20)
        # part_svg_options = {"showAxes": False, "marginLeft": 20}
        for checksum, catalog_item in project.inventory.catalog.items.items():
            part = project.inventory.parts[checksum]
            part_names.add(catalog_item.name)
            svg_path = assets_path / f"{catalog_item.name}.svg"
            if not index or index and checksum in index.is_part_modified or not svg_path.exists():
                logger.info(f"- Generating SVG for part '{catalog_item.name}'")
                svg = AssetHelper.getSVG(part, part_svg_options)
                # svg = getSVG(part, part_svg_options)

                with open(svg_path, "w") as f:
                    f.write(svg)


        # Generate assets for main assembly
        with open(inventory_path / "README.md", "w") as f:
            inventory_md = CadService.get_inventory_markdown(project.inventory, assets_path)
            f.write(inventory_md)

        # Generate SVG for root assembly
        root_assembly_svg_path = assets_path / f"{project.root_assembly.long_name}.svg"
        if not index or index and project.root_assembly.path in index.is_assembly_modified or not root_assembly_svg_path.exists():
            logger.info(f"- Generating SVG for root assembly '{project.root_assembly.name}', this may take a sec ...")
            root_assembly_cq = project.root_assembly.to_cq(project)
            assembly_svg_options = SVGOptions(showAxes=False, marginLeft=20, showHidden=False, strokeWidth=-0.9)
            # assembly_svg_options = {"showAxes": False, "marginLeft": 20, "showHidden": False, "strokeWidth": -0.9}
            root_assembly_svg = AssetHelper.getSVG(root_assembly_cq, assembly_svg_options)
            # root_assembly_svg = getSVG(root_assembly_cq.toCompound(), assembly_svg_options)

            with open(root_assembly_svg_path, "w") as f:
                f.write(root_assembly_svg)

        logger.info("\n\n- Removing SVG files not in inventory")
        for svg_path in assets_path.glob("*.svg"):
            if svg_path.stem not in part_names and svg_path != root_assembly_svg_path:
                svg_path.unlink()



    @staticmethod
    def write_assemblies(project_path: Union[Path, str], project: Project, verbose=False):
        logger.setLevel(logging.INFO if verbose else logging.ERROR)

        project_path = Path(project_path)
        assembly_path = project_path / ASSEMBLY_DIRECTORY

        logger.info(f"Writing assemblies to {assembly_path}")

        # delete directory path
        if project_path.is_dir() and assembly_path.is_dir():
                shutil.rmtree(assembly_path)
        assembly_path.mkdir(parents=True, exist_ok=True)

        # Generate assembly files
        for assembly in project.assemblies.values():
            subassembly_path = assembly_path / assembly.path.lstrip("/")
            subassembly_path.mkdir(parents=True, exist_ok=True)
            with open(subassembly_path / "assembly.json", "w") as f:
                f.write(assembly.model_dump_json(indent=4))
    

    # TODO: start breaking the function into smaller parts
    @staticmethod
    def write_project(project_path: Union[Path, str], project: Project, index: Optional[AssemblyIndex] = None, verbose=False):
        logger.setLevel(logging.INFO if verbose else logging.ERROR)
        
        logger.info(f"\n\nWriting project to {project_path}")
        project_path = Path(project_path)
        project_path.mkdir(parents=True, exist_ok=True)

        # Write inventory
        logger.info(f"\n\n")
        CadService.write_inventory(project_path, project.inventory, verbose)

        # Write assemblies
        logger.info(f"\n\n")
        CadService.write_assemblies(project_path, project, verbose)

        # Write assets
        if project.options.include_assets:
            logger.info(f"\n\n")
            CadService.write_assets(project_path, project, index, verbose)


    @staticmethod
    def create_project(
        project_path: Optional[Path] = None,
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
            CadService.read_cq_assembly(cq_assembly, project)
        if project_path:
            CadService.write_project(project_path, project, verbose=verbose)
        return project

    @staticmethod
    def revise_project(project_path: Path, cad_path: Path, write=False, project_options: Optional[ProjectOptions] = None, verbose=False):
        logger.setLevel(logging.INFO if verbose else logging.ERROR)

        prev_project = CadService.read_project(project_path)

        cq_assembly = CadHelper.import_step(cad_path)

        revised_project = Project()
        if project_options:
            revised_project.options = project_options
        index = AssemblyIndex(prev_project=prev_project)
        CadService.read_cq_assembly(cq_assembly, revised_project, index)

        if write:
            CadService.write_project(project_path, revised_project, verbose=verbose)
        
        return revised_project

    @staticmethod
    def read_project(project_path: Union[Path, str]):
        project = Project()

        project_path = Path(project_path)
        assert project_path.is_dir(), f"Project directory not found: {project_path}"
        inventory_path = project_path / INVENTORY_DIRECTORY
        parts_path = inventory_path / "parts"

        with open(inventory_path / "catalog.json", "r") as f:
            catalog = InventoryCatalog.model_validate_json(f.read())
            for checksum, catalog_item in catalog.items.items():
                catalog_item = CatalogItem.model_validate(catalog_item)
                brep_path = parts_path / f"{catalog_item.name}.brep"
                project.inventory.parts[checksum] = cq.Solid(
                    CadHelper.import_brep(brep_path)
                )
                project.inventory.catalog.items[checksum] = catalog_item

        assembly_path = project_path / ASSEMBLY_DIRECTORY

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
