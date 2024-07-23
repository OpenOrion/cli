from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Optional, OrderedDict, Union
import click
import numpy as np
import cadquery as cq
from pydantic import BaseModel, Field
from scipy.spatial.transform import Rotation as R
import shutil
import cadquery as cq
from orion_cli.helpers.cad_helper import CadHelper


# Parameter Labels
PartSurfaceArea = float
PartNumVertices = int
PartGroup = tuple[PartSurfaceArea, PartNumVertices]
PartChecksum = str
AlignedPartChecksum = str
PartSlug = str
AssemblyPath = str



@dataclass
class Inventory:
    """
    Catalog of all parts in the project
    """
    parts: dict[PartChecksum, cq.Solid] = field(default_factory=dict)
    slugs: dict[PartChecksum, PartSlug] = field(default_factory=dict)


class PartRef(BaseModel):
    """
    Reference to a part in the inventory with a specific position and orientation (rotation matrix)
    """
    path: str
    checksum: str
    position: list[float]
    orientation: list[list[float]]
    color: Optional[list] = None

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
            part = project.inventory.parts[part_ref.checksum]
            loc = CadHelper.get_location(part_ref.orientation, part_ref.position)
            
            # TODO: find a better solution to handle negative rotation determinants (mirrors)
            if loc.wrapped.Transformation().IsNegative():
                aligned_part = CadHelper.transform_solid(part, part_ref.orientation,part_ref.position)
                cq_assembly.add(aligned_part, color=cq.Color(*part_ref.color), name=part_ref.name)
            else:
                cq_assembly.add(
                    part, color=cq.Color(*part_ref.color), name=part_ref.name, loc=loc
                )

        return cq_assembly

class ProjectOptions(BaseModel):
    max_slug_depth: int = 3
    normalize_axis: bool = False
    use_references: bool = True

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
    slugs: dict[PartSlug, Optional[PartRef]] = field(default_factory=dict)

    # revisioning    
    prev_project: Optional["Project"] = None
    is_modified: set[AssemblyPath] = field(default_factory=set)

class CadService:
    @staticmethod
    def read_cqassembly(
        cq_assembly: cq.Assembly,
        project: Project,
        index: Optional[AssemblyIndex] = None,
        use_references: bool = True,
        curr_path: str = "",
    ):
        if index is None:
            index = AssemblyIndex()
        if curr_path == "":
            index.is_modified.clear()

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
                    root_assembly.path,
                )
                root_assembly.add_child(subassemblies[0])
                assemblies.extend(subassemblies)
                is_modified = is_modified or is_sub_modified
                if is_modified:
                    index.is_modified.add(root_assembly.path)

            else:
                base_part, part_ref = CadService.get_part(
                    cq_subassembly, root_assembly.path, index, project.options
                )

                is_modified = not(
                    # has the path been previously indexed
                    index.prev_project and part_ref.path in index.prev_project.part_refs and 
                    # if the part checksum is the same
                    index.prev_project.part_refs[part_ref.path].checksum == part_ref.checksum
                )

                CadService.set_unique_slug(part_ref, project, index)

                root_assembly.parts.append(part_ref)
                project.part_refs[part_ref.path] = part_ref

                if part_ref.checksum not in project.inventory.parts:
                    project.inventory.parts[part_ref.checksum] = base_part

        return assemblies, is_modified

    @staticmethod
    def set_unique_slug(part_ref: PartRef, project: Project, index: AssemblyIndex):
        slug = part_ref.name
        # check if slug already exists
        if slug in index.slugs:
            if part_ref.checksum != index.slugs[slug].checksum:
                # going back and modifying the previous part slug
                prev_part_ref = index.slugs[slug]
                prev_path_strs = prev_part_ref.path.split("/")
                prev_slug = '-'.join(prev_path_strs[min(project.options.max_slug_depth, len(prev_path_strs)):])
                assert prev_slug not in index.slugs, f"slug {prev_slug} already exists"
                project.inventory.slugs[prev_part_ref.checksum] = prev_slug

                # modifying the current part slug
                path_strs = part_ref.path.split("/")
                slug = '-'.join(path_strs[min(project.options.max_slug_depth, len(path_strs)):])
                assert slug not in index.slugs, f"slug {slug} already exists"
                project.inventory.slugs[part_ref.checksum] = slug

        else:
            # add slug to index with part_ref it pertains to
            index.slugs[slug] = part_ref
            project.inventory.slugs[part_ref.checksum] = slug

    @staticmethod
    def get_part(
        cq_subassembly: cq.Assembly,
        assembly_path: str,
        index: Optional[AssemblyIndex] = None,
        options: Optional[ProjectOptions] = None,
    ):
        is_reference = (options and options.use_references) and cq_subassembly.metadata.get(
            "is_reference", False
        )
        if is_reference:
            return CadService.get_referenced_part(cq_subassembly, assembly_path)
        else:
            normalize_axis=options is not None and options.normalize_axis
            return CadService.get_non_reference_part(cq_subassembly, assembly_path, index, normalize_axis)

    @staticmethod
    def get_referenced_part(cq_subassembly: cq.Assembly, assembly_path: str):
        base_part: cq.Solid = cq_subassembly.obj.val()
        translation, euler_angles = cq_subassembly.loc.toTuple()
        rotmat = R.from_euler("xyz", euler_angles, degrees=True).as_matrix()
        part_checksum = CadHelper.get_part_checksum(base_part)

        part_ref = PartRef(
            path=f"{assembly_path}/{cq_subassembly.name}",
            checksum=part_checksum,
            position=list(translation),
            orientation=rotmat.tolist(),
            color=list(cq_subassembly.color.toTuple()),
        )
        return base_part, part_ref

    @staticmethod
    def get_non_reference_part(
        cq_subassembly: cq.Assembly, assembly_path: str, index: Optional[AssemblyIndex] = None, normalize_axis: bool = False
    ):
        if index is None:
            index = AssemblyIndex()
        aligned_part = cq_subassembly.obj.val().located(cq_subassembly.loc)

        # check if part has been aligned before
        # if index.prev_project:
        #     aligned_checksum = CadHelper.get_part_checksum(aligned_part)

        #     if aligned_checksum in index.aligned_refs:
        #         part_ref = index.aligned_refs[aligned_checksum]
        #         base_part = index.prev_project.inventory.parts[part_ref.checksum]
        #         return base_part, part_ref

        #     index.aligned_refs[aligned_checksum] = part_ref

        # otherwise align part and normalize
        part_group = (
            np.round(aligned_part.Area(), 3),
            len(aligned_part._entities("Vertex")),
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

        part_ref = PartRef(
            path=f"{assembly_path}/{cq_subassembly.name}",
            checksum=part_checksum,
            position=offset.tolist(),
            orientation=rotmat.tolist(),
            color=list(cq_subassembly.color.toTuple()),
        )
        return base_part, part_ref


    @staticmethod
    def write_project(project_path: Union[Path, str], project: Project): #, index: Optional[AssemblyIndex] = None):
        project_path = Path(project_path)
        project_path.mkdir(parents=True, exist_ok=True)
        assembly_path = project_path / "assemblies"
        # assets_path = project_path / "assets"
        inventory_path = project_path / "inventory"

        # delete directory path
        if project_path.is_dir():
            if assembly_path.is_dir():
                shutil.rmtree(assembly_path)
            if inventory_path.is_dir():
                shutil.rmtree(inventory_path)

        inventory_path.mkdir(parents=True, exist_ok=True)
        assembly_path.mkdir(parents=True, exist_ok=True)

        part_checksum_to_slug = {}
        for checksum, part in project.inventory.parts.items():
            part_slug = project.inventory.slugs[checksum]
            part_checksum_to_slug[checksum] = part_slug
            brep_path = inventory_path / f"{part_slug}.brep"
            with open(brep_path, "w") as f:
                CadHelper.export_brep(part.wrapped, f"{brep_path}")

        with open(inventory_path / "parts.json", "w") as f:
            json.dump(part_checksum_to_slug, f, indent=4)

        for assembly in project.assemblies.values():
            subassembly_path = assembly_path / assembly.path.lstrip("/")
            subassembly_path.mkdir(parents=True, exist_ok=True)
            
            # if index and assembly.path in index.is_modified:
            #     asm_compound = cq_subassembly.toCompound()
            #     asset_name = "-".join(assembly.path.split("/"))
            #     exporters.export(asm_compound, str(assets_path / f"{asset_name}.svg"))


            with open(subassembly_path / "assembly.json", "w") as f:
                f.write(assembly.model_dump_json(indent=4))
    
    @staticmethod
    def create_project(
        project_path: Path,
        step_file: Optional[Path] = None,
        project_options: Optional[ProjectOptions] = None
    ):
        project = Project()
        if project_options:
            project.options = project_options
        if step_file:
            # Create the new directory
            click.echo(f"Loading in step file {step_file}")
            cq_assembly = CadHelper.import_step(step_file)
            CadService.read_cqassembly(cq_assembly, project)
        CadService.write_project(project_path, project)

    @staticmethod
    def revise_project(project_path: Path, cad_path: Path, write=False, project_options: Optional[ProjectOptions] = None):
        prev_project = CadService.read_project(project_path)

        cq_assembly = CadHelper.import_step(cad_path)

        revised_project = Project()
        if project_options:
            revised_project.options = project_options
        index = AssemblyIndex(prev_project=prev_project)
        CadService.read_cqassembly(cq_assembly, revised_project, index)

        if write:
            CadService.write_project(project_path, revised_project)
        return revised_project

    @staticmethod
    def read_project(project_path: Union[Path, str]):
        project = Project()

        project_path = Path(project_path)
        assert project_path.is_dir(), f"Project directory not found: {project_path}"
        inventory_path = project_path / "inventory"
        with open(inventory_path / "parts.json", "r") as f:
            slugs = dict(json.load(f))
            for checksum, slug in slugs.items():
                brep_path = inventory_path / f"{slug}.brep"
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
    def visualize_project(project_path: Union[Path, str]):
        from jupyter_cadquery.viewer import show
        project_path = Path(project_path)
        project = CadService.read_project(project_path)
        show(project.root_assembly.to_cq(project))
