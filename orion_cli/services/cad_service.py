from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Optional, OrderedDict, Union
import numpy as np
import cadquery as cq
from pydantic import BaseModel, Field
from scipy.spatial.transform import Rotation as R
import shutil
import cadquery as cq
from orion_cli.helpers.cad_helper import CadHelper


class PartRef(BaseModel):
    path: str
    checksum: str
    position: list[float]
    orientation: list[list[float]]
    color: Optional[list] = None

    @property
    def name(self):
        return self.path.split("/")[-1]


class Assembly(BaseModel):
    path: str
    children: list[str] = Field(default_factory=list)
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
            loc = cq.Location(
                cq.Vector(*part_ref.position),
                tuple(
                    R.from_matrix(part_ref.orientation)
                    .as_euler("xyz", degrees=True)
                    .tolist()
                ),
            )
            cq_assembly.add(
                part, color=cq.Color(*part_ref.color), name=part_ref.name, loc=loc
            )
        return cq_assembly


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
    parts: dict[PartChecksum, cq.Solid] = field(default_factory=dict)
    slugs: dict[PartChecksum, PartSlug] = field(default_factory=dict)


@dataclass
class Project:
    assemblies: OrderedDict[AssemblyPath, Assembly] = field(default_factory=OrderedDict)
    part_refs: OrderedDict[AssemblyPath, PartRef] = field(default_factory=OrderedDict)
    inventory: Inventory = field(default_factory=Inventory)

    @property
    def root_assembly(self):
        return next(iter(self.assemblies.values()))


@dataclass
class PartIndex:
    base_parts: dict[PartGroup, cq.Solid] = field(default_factory=dict)
    aligned_refs: dict[AlignedPartChecksum, PartRef] = field(default_factory=dict)
    slugs: dict[PartSlug, Optional[PartRef]] = field(default_factory=dict)
    prev_project: Optional["Project"] = None


class CadService:
    @staticmethod
    def read_cqassembly(
        cq_assembly: cq.Assembly,
        project: Project,
        part_index: Optional[PartIndex] = None,
        use_references: bool = True,
        curr_path: str = "",
    ):
        if part_index is None:
            part_index = PartIndex()

        is_changed = False
        root_assembly = Assembly(path=curr_path + f"/{cq_assembly.name}")
        assemblies = [root_assembly]
        project.assemblies[root_assembly.path] = root_assembly

        for cq_subassembly in cq_assembly.children:
            if isinstance(cq_subassembly, cq.Assembly) and len(cq_subassembly.children):
                subassemblies, child_is_changed = CadService.read_cqassembly(
                    cq_subassembly,
                    project,
                    part_index,
                    use_references,
                    root_assembly.path,
                )
                root_assembly.add_child(subassemblies[0])
                assemblies.extend(subassemblies)
                is_changed = is_changed or child_is_changed
            else:
                base_part, part_ref = CadService.get_part(
                    cq_subassembly, root_assembly.path, part_index, use_references
                )

                is_changed = not(part_ref.path in project.part_refs and project.part_refs[part_ref.path].checksum == part_ref.checksum)
                CadService.set_unique_slug(part_ref, project, part_index)

                root_assembly.parts.append(part_ref)
                project.part_refs[part_ref.path] = part_ref

                if part_ref.checksum not in project.inventory.parts:
                    project.inventory.parts[part_ref.checksum] = base_part

        return assemblies, is_changed

    @staticmethod
    def set_unique_slug(part_ref: PartRef, project: Project, part_index: PartIndex, max_slug_depth=3):
        slug = part_ref.name
        if slug in part_index.slugs:
            if part_ref.checksum != part_index.slugs[slug].checksum:
                prev_part_ref = part_index.slugs[slug]
                prev_path_strs = prev_part_ref.path.split("/")
                prev_slug = '-'.join(prev_path_strs[min(max_slug_depth, len(prev_path_strs)):])
                assert prev_slug not in part_index.slugs, f"slug {prev_slug} already exists"
                project.inventory.slugs[prev_part_ref.checksum] = prev_slug

                path_strs = part_ref.path.split("/")
                slug = '-'.join(path_strs[min(max_slug_depth, len(path_strs)):])
                assert slug not in part_index.slugs, f"slug {slug} already exists"
                project.inventory.slugs[part_ref.checksum] = slug

        else:
            part_index.slugs[slug] = part_ref
            project.inventory.slugs[part_ref.checksum] = slug

    @staticmethod
    def get_part(
        cq_subassembly: cq.Assembly,
        assembly_path: str,
        part_index: Optional[PartIndex] = None,
        use_references: bool = True,
    ):
        is_reference = use_references and cq_subassembly.metadata.get(
            "is_reference", False
        )
        if is_reference:
            return CadService.get_referenced_part(cq_subassembly, assembly_path)
        else:
            return CadService.get_non_reference_part(cq_subassembly, assembly_path, part_index)

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
        cq_subassembly: cq.Assembly, assembly_path: str, part_index: Optional[PartIndex] = None
    ):
        if part_index is None:
            part_index = PartIndex()

        # check if part has been aligned before
        if part_index.prev_project:
            aligned_part = cq_subassembly.obj.val().located(cq_subassembly.loc)
            aligned_checksum = CadHelper.get_part_checksum(aligned_part)

            if aligned_checksum in part_index.aligned_refs:
                part_ref = part_index.aligned_refs[aligned_checksum]
                base_part = part_index.prev_project.inventory.parts[part_ref.checksum]
                return base_part, part_ref

            part_index.aligned_refs[aligned_checksum] = part_ref

        # otherwise align part and normalize
        aligned_part = cq_subassembly.obj.val().located(cq_subassembly.loc)
        part_group = (
            np.round(aligned_part.Area(), 3),
            len(aligned_part._entities("Vertex")),
        )
        base_part, offset, rotmat = CadHelper.normalize_part_with_inertial_axis(aligned_part)

        # check if part has been normalized before
        if part_group not in part_index.base_parts:
            part_index.base_parts[part_group] = base_part
        else:
            # align part with previously normalized part (in case of symetric inertial axis)
            base_part = part_index.base_parts[part_group]
            rot_mat_adjustment = CadHelper.align_parts(base_part, base_part)
            rotmat = rotmat.dot(rot_mat_adjustment)

        part_checksum = CadHelper.get_part_checksum(base_part)
        part_ref = PartRef(
            path=f"{assembly_path}/{cq_subassembly.name}",
            checksum=part_checksum,
            position=offset.tolist(),
            orientation=rotmat.tolist(),
            color=list(cq_subassembly.color.toTuple()),
        )
        return base_part, part_ref


    @staticmethod
    def write_project(project_path: Union[Path, str], project: Project):
        project_path = Path(project_path)
        project_path.mkdir(parents=True, exist_ok=True)
        assembly_path = project_path / "assemblies"

        # delete directory path
        if project_path.is_dir():
            shutil.rmtree(project_path)

        inventory_path = project_path / "inventory"
        inventory_path.mkdir(parents=True, exist_ok=True)

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
            with open(subassembly_path / "assembly.json", "w") as f:
                f.write(assembly.model_dump_json(indent=4))

    @staticmethod
    def read_project(proj_path: Union[Path, str]):
        project = Project()

        proj_path = Path(proj_path)
        inventory_path = proj_path / "inventory"
        with open(inventory_path / "parts.json", "r") as f:
            slugs = dict(json.load(f))
            for checksum, slug in slugs.items():
                brep_path = inventory_path / f"{slug}.brep"
                project.inventory.parts[checksum] = cq.Solid(
                    CadHelper.import_brep(brep_path)
                )

        assembly_path = proj_path / "assemblies"

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
