from dataclasses import dataclass, field
from functools import cached_property
import hashlib
import json
from pathlib import Path
from typing import Optional, Union
import numpy as np
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS_Shape
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf
from OCP.BRepTools import BRepTools
from OCP.BRep import BRep_Builder
import cadquery as cq
from pydantic import BaseModel, Field
from OCP.BRepGProp import BRepGProp
from scipy.spatial.transform import Rotation as R
import shutil
from ocp_tessellate.tessellator import Tessellator, compute_quality
from ocp_tessellate.ocp_utils import bounding_box, get_location
import cadquery as cq
# from jupyter_cadquery import show
# from jupyter_cadquery.viewer import show

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

    def add_child(self, child: Union["Assembly", "AssemblyCollection"]):
        if isinstance(child, Assembly):
            self.children.append(child.path)
        elif isinstance(child, AssemblyCollection):
            self.children.append(child.root_assembly.path)

    @property
    def name(self):
        return self.path.split("/")[-1]

class AssemblyCollection(BaseModel):
    root_assembly: Assembly
    subassemblies: list[Assembly] = Field(default_factory=list)

    @cached_property
    def path_map(self):
        return {assembly.path: assembly for assembly in self.assemblies}

    def __getitem__(self, path: str):
        return self.path_map[path]

    @property
    def assemblies(self):
        return [self.root_assembly] + self.subassemblies

    @property
    def parts(self):
        return [part for assembly in self.assemblies for part in assembly.parts]

    def combine(self, other: "AssemblyCollection"):        
        return AssemblyCollection(root_assembly=self.root_assembly, subassemblies=self.subassemblies + [other.root_assembly] + other.subassemblies)

    def add(self, subassemblies: Union["AssemblyCollection", list[Assembly], Assembly]):
        if isinstance(subassemblies, AssemblyCollection):
            self.subassemblies += subassemblies.assemblies
        elif isinstance(subassemblies, Assembly):
            self.subassemblies.append(subassemblies)
        else:
            self.subassemblies += subassemblies


    def __iter__(self):
        return iter(self.assemblies)

# (surface area, num vertices)
PartSurfaceArea = float
PartNumVertices = int
PartGroup = tuple[PartSurfaceArea, PartNumVertices]
PartChecksum = str
AlignedPartChecksum = str
PartSlug = str

@dataclass
class Inventory:
    parts: dict[PartChecksum, cq.Solid] = field(default_factory=dict)
    slugs: dict[PartChecksum, PartSlug] = field(default_factory=dict)

@dataclass
class AssemblyIndex:
    curr_path: str = ""
    base_parts: dict[PartGroup, cq.Solid] = field(default_factory=dict)
    part_refs: dict[AlignedPartChecksum, PartRef] = field(default_factory=dict)
    prev_inventory: Optional[Inventory] = None
    prev_slugs: dict[PartSlug, Optional[PartRef]] = field(default_factory=dict)

@dataclass
class Project:
    inventory: Inventory
    assemblies: AssemblyCollection
    cq_assembly: cq.Assembly
    assembly_index: AssemblyIndex

@dataclass
class InertialAxisNormalizedPartResult:
    part: cq.Solid
    offset: np.ndarray
    rotmat: np.ndarray
    has_symetric_axis: bool

@dataclass
class Mesh:
    vertices: np.ndarray
    simplices: np.ndarray
    normals: np.ndarray
    edges: np.ndarray


class CadService:
    @staticmethod
    def tesselate_shape(shape: cq.Solid):
        tess = Tessellator("")

        bb = bounding_box(shape.wrapped, loc=get_location(None), optimal=False)
        quality = compute_quality(bb, deviation=0.1)

        tess.compute(
            shape.wrapped, quality, angular_tolerance=0.2, compute_faces=True, compute_edges=True, debug=False
        )
        tri_vertices = tess.get_vertices().reshape(-1,3)
        tri_indices = tess.get_triangles().reshape(-1,3)
        tri_normals = tess.get_normals().reshape(-1,3)
        edges = tess.get_edges().reshape(-1,2,3)
        return Mesh(vertices=tri_vertices, simplices=tri_indices, normals=tri_normals, edges=edges)

    def transform_solid(solid: cq.Solid, orientation: np.ndarray, offset: Optional[np.ndarray] = None):
        if offset is None:
            offset = np.zeros(3)
        # Create a transformation object
        transformation = gp_Trsf()
        transformation.SetValues(orientation[0][0], orientation[0][1], orientation[0][2], offset[0],
                                orientation[1][0], orientation[1][1], orientation[1][2], offset[1],
                                orientation[2][0], orientation[2][1], orientation[2][2], offset[2])


        # Apply the transformation to the box
        transformer = BRepBuilderAPI_Transform(solid.wrapped, transformation, True)
        return cq.Solid(transformer.Shape())


    @staticmethod
    def import_brep(file_path: Union[Path, str]):
        """
        Import a boundary representation model
        Returns a TopoDS_Shape object
        """
        builder = BRep_Builder()
        shape = TopoDS_Shape()
        return_code = BRepTools.Read_s(shape, str(file_path), builder)
        if return_code is False:
            raise ValueError("Import failed, check file name")
        return shape

    @staticmethod
    def export_brep(shape: TopoDS_Shape, file_path: str):
        BRepTools.Write_s(shape, file_path)

    @staticmethod
    def normalize_part_with_inertial_axis(solid: cq.Solid):
        offset = np.array(solid.Center().toTuple())
        centered_solid = solid.translate((-offset).tolist())
        
        curr_solid = centered_solid        
        has_symetric_axis = False
        rotmat_axis_of_inertia = np.eye(3)
        for axis_index in range(2):
            axis_vector = np.zeros(3)
            axis_vector[axis_index] = 1

            Properties = GProp_GProps()
            BRepGProp.VolumeProperties_s(curr_solid.wrapped, Properties)
            principle_properties = Properties.PrincipalProperties()

            has_symetric_axis = principle_properties.HasSymmetryAxis()
            
            axis_of_inertias_occ = (
                principle_properties.FirstAxisOfInertia(),
                principle_properties.SecondAxisOfInertia(),
                principle_properties.ThirdAxisOfInertia()
            )

            axis_of_inertias = np.array([
                (axis_of_inertias_occ[0].X(), axis_of_inertias_occ[0].Y(), axis_of_inertias_occ[0].Z()),
                (axis_of_inertias_occ[1].X(), axis_of_inertias_occ[1].Y(), axis_of_inertias_occ[1].Z()),
                (axis_of_inertias_occ[2].X(), axis_of_inertias_occ[2].Y(), axis_of_inertias_occ[2].Z())
            ])

            # Ensure the first principal component points in the positive x-direction
            if axis_of_inertias[0, 0] < 0:
                axis_of_inertias[0] = -axis_of_inertias[0]
            # Ensure the second principal component points in the positive y-direction
            if axis_of_inertias[1, 1] < 0:
                axis_of_inertias[1] = -axis_of_inertias[1]
            # Ensure the third principal component points in the positive z-direction
            if axis_of_inertias[2, 2] < 0:
                axis_of_inertias[2] = -axis_of_inertias[2]

            rotmat_axis_of_inertia = axis_of_inertias.dot(rotmat_axis_of_inertia)
            curr_solid  = CadService.transform_solid(curr_solid, axis_of_inertias)
        rotmat = rotmat_axis_of_inertia.T
        return InertialAxisNormalizedPartResult(curr_solid, offset, rotmat, has_symetric_axis)

    @staticmethod
    def align_parts(part1: cq.Solid, part2: cq.Solid):
        vertices1 = np.array([vertex.toTuple() for vertex in part1.Vertices()])
        vertices2 = np.array([vertex.toTuple() for vertex in part2.Vertices()])

        assert len(vertices1) == len(vertices2), "part1 and part2 are different"

        # Center the vertices to the origin
        centroid1 = np.mean(vertices1, axis=0)
        centroid2 = np.mean(vertices2, axis=0)
        vertices1_centered = vertices1 - centroid1
        vertices2_centered = vertices2 - centroid2

        # Compute covariance matrix
        H = np.dot(vertices2_centered.T, vertices1_centered)

        # Singular Value Decomposition (SVD)
        U, S, Vt = np.linalg.svd(H)
        rotmat = np.dot(Vt.T, U.T)

        # Ensure the rotation matrix is proper (determinant should be +1)
        # if np.linalg.det(rotation_matrix) < 0:
        #     Vt[2, :] *= -1
        #     rotation_matrix = np.dot(Vt.T, U.T)

        solid2_aligned_vertices = np.dot(vertices2, rotmat)
        error = np.sum(np.sum(vertices1 - solid2_aligned_vertices, axis=0))
        if error < 1E-3:
            return rotmat

        raise ValueError("failed to align parts")

    @staticmethod
    def process_assembly(cq_assembly: Union[cq.Assembly, cq.Workplane], inventory: Inventory, index: Optional[AssemblyIndex] = None, use_references: bool = True) -> AssemblyCollection:
        if index is None:
            index = AssemblyIndex(curr_path="")

        old_path = index.curr_path
        new_path = index.curr_path + f"/{cq_assembly.name}"
        root_assembly = Assembly(path=new_path)
        assemblies = AssemblyCollection(root_assembly=root_assembly)

        index.curr_path = new_path
        for cq_subassembly in cq_assembly.children:
            if isinstance(cq_subassembly, cq.Assembly) and len(cq_subassembly.children):
                child_assemblies = CadService.process_assembly(cq_subassembly, inventory, index, use_references)
                root_assembly.add_child(child_assemblies)
                assemblies.add(child_assemblies)
            else:
                base_part, part_ref = CadService.get_part(cq_subassembly, index, use_references)

                CadService.set_unique_slug(part_ref, inventory, index)
                
                if part_ref.checksum not in inventory.parts:
                    inventory.parts[part_ref.checksum] = base_part
                root_assembly.parts.append(part_ref)
        index.curr_path = old_path

        return assemblies

    @staticmethod
    def set_unique_slug(part_ref: PartRef, inventory: Inventory, index: AssemblyIndex, max_slug_depth=3):
        slug = part_ref.name
        if slug in index.prev_slugs:
            if part_ref.checksum != index.prev_slugs[slug].checksum:
                prev_part_ref = index.prev_slugs[slug]
                prev_path_strs = prev_part_ref.path.split("/")
                prev_slug = '-'.join(prev_path_strs[min(max_slug_depth, len(prev_path_strs)):])
                assert prev_slug not in index.prev_slugs, f"slug {prev_slug} already exists"
                inventory.slugs[prev_part_ref.checksum] = prev_slug
                
                path_strs = part_ref.path.split("/")
                slug = '-'.join(path_strs[min(max_slug_depth, len(path_strs)):])
                assert slug not in index.prev_slugs, f"slug {slug} already exists"
                inventory.slugs[part_ref.checksum] = slug

        else:
            index.prev_slugs[slug] = part_ref
            inventory.slugs[part_ref.checksum] = slug

    @staticmethod
    def get_part(cq_subassembly: cq.Assembly, assembly_index: AssemblyIndex, use_references: bool):
        is_reference = use_references and cq_subassembly.metadata.get("is_reference", False)
        if is_reference:
            return CadService.get_referenced_part(cq_subassembly, assembly_index)
        else:
            return CadService.get_non_reference_part(cq_subassembly, assembly_index)

    @staticmethod
    def get_referenced_part(cq_subassembly: cq.Assembly, assembly_index: AssemblyIndex):
        base_part: cq.Solid = cq_subassembly.obj.val()
        translation, euler_angles = cq_subassembly.loc.toTuple()
        rotmat = R.from_euler("xyz", euler_angles, degrees=True).as_matrix()
        part_checksum = CadService.get_part_checksum(base_part)

        part_ref = PartRef(
            path= f"{assembly_index.curr_path}/{cq_subassembly.name}",
            checksum=part_checksum,
            position=list(translation),
            orientation=rotmat.tolist(),
            color=list(cq_subassembly.color.toTuple())
        )
        return base_part, part_ref

    @staticmethod
    def get_non_reference_part(cq_subassembly: cq.Assembly, assembly_index: AssemblyIndex):
        # check if part has been aligned before
        if assembly_index.prev_inventory:
            aligned_part = cq_subassembly.obj.val().located(cq_subassembly.loc)
            aligned_part_checksum = CadService.get_part_checksum(aligned_part)

            if aligned_part_checksum in assembly_index.part_refs:
                part_ref = assembly_index.part_refs[aligned_part_checksum]
                base_part = assembly_index.prev_inventory.parts[part_ref.checksum]
                return base_part, part_ref
            
            assembly_index.part_refs[aligned_part_checksum] = part_ref
        
        base_part, part_ref = CadService.normalize_and_align_part(cq_subassembly, assembly_index)

        return base_part, part_ref
    
    @staticmethod
    def normalize_and_align_part(cq_subassembly: cq.Assembly, assembly_index: AssemblyIndex):
        aligned_part = cq_subassembly.obj.val().located(cq_subassembly.loc)

        part_index = (np.round(aligned_part.Area(), 3), len(aligned_part._entities("Vertex")))
        normalized_result = CadService.normalize_part_with_inertial_axis(aligned_part)
        base_part, offset, rotmat = normalized_result.part, normalized_result.offset, normalized_result.rotmat

        # check if part has been normalized before
        if part_index not in assembly_index.base_parts:
            assembly_index.base_parts[part_index] = base_part
        else:
            # align part with previously normalized part (in case of symetric inertial axis)
            base_part = assembly_index.base_parts[part_index]
            rot_mat_adjustment = CadService.align_parts(base_part, base_part)
            rotmat = rotmat.dot(rot_mat_adjustment)

        part_checksum = CadService.get_part_checksum(base_part)
        part_ref = PartRef(
            path= f"{assembly_index.curr_path}/{cq_subassembly.name}",
            checksum=part_checksum,
            position=offset.tolist(),
            orientation=rotmat.tolist(),
            color=list(cq_subassembly.color.toTuple())
        )
        return base_part, part_ref

    @staticmethod
    def write_assemblies(assemblies: Union[AssemblyCollection, list[Assembly]], inventory: Inventory, proj_path: Union[Path, str]):
        proj_path = Path(proj_path)
        proj_path.mkdir(parents=True, exist_ok=True)
        assembly_path = proj_path / "assemblies"
        
        # delete directory path
        if proj_path.is_dir():
            shutil.rmtree(proj_path)

        inventory_path = proj_path / "inventory"
        inventory_path.mkdir(parents=True, exist_ok=True)
        
        part_checksum_to_slug = {}
        for checksum, part in inventory.parts.items():
            part_slug = inventory.slugs[checksum]
            part_checksum_to_slug[checksum] = part_slug
            brep_path = inventory_path / f"{part_slug}.brep"
            with open(brep_path, "w") as f:
                CadService.export_brep(part.wrapped, f"{brep_path}")

        with open(inventory_path / "parts.json", "w") as f:
            json.dump(part_checksum_to_slug, f, indent=4)

        for assembly in assemblies:
            subassembly_path = assembly_path / assembly.path.lstrip("/")
            subassembly_path.mkdir(parents=True, exist_ok=True)
            with open(subassembly_path / "assembly.json", "w") as f:
                f.write(assembly.model_dump_json(indent=4))

    @staticmethod
    def read_assemblies(proj_path: Union[Path, str], inventory: Inventory):
        proj_path = Path(proj_path)
        inventory_path = proj_path / "inventory"
        with open(inventory_path / "parts.json", "r") as f:
            slugs = dict(json.load(f))
            for checksum, slug in slugs.items():
                brep_path = inventory_path / f"{slug}.brep"
                inventory.parts[checksum] = cq.Solid(CadService.import_brep(brep_path))

        assemblies = []
        root_assembly = None
        assembly_path = proj_path / "assemblies"

        for assembly_file_path in assembly_path.rglob("assembly.json"):
            if assembly_file_path.is_file():
                with open(assembly_file_path, "r") as f:                        
                    assembly = Assembly.model_validate_json(f.read())
                    assemblies.append(assembly)
                    if root_assembly is None:
                        root_assembly = assembly

        return AssemblyCollection(root_assembly=root_assembly, subassemblies=assemblies)

    @staticmethod
    def cq_reassemble(assemblies: AssemblyCollection, inventory: Inventory, assembly_index: Optional[AssemblyIndex] = None, curr_assembly: Optional[Assembly] = None):
        if assembly_index is None:
            assembly_index = AssemblyIndex()
        if curr_assembly is None:
            curr_assembly = assemblies.root_assembly
        cq_assembly = cq.Assembly(name=curr_assembly.name)
        for subassembly_path in curr_assembly.children:
            subassembly = assemblies[subassembly_path]
            cq_assembly.add(CadService.cq_reassemble(assemblies, inventory, assembly_index, assemblies.path_map[subassembly_path]), name=subassembly.name)
        for part_ref in curr_assembly.parts:
            part = inventory.parts[part_ref.checksum]
            # TODO: make this by loc reference
            aligned_part = CadService.transform_solid(part, part_ref.orientation, part_ref.position)
            aligned_part_checksum = CadService.get_part_checksum(aligned_part)
            assembly_index.part_refs[aligned_part_checksum] = part_ref
            loc = cq.Location(cq.Vector(*part_ref.position), tuple(R.from_matrix(part_ref.orientation).as_euler("xyz", degrees=True).tolist()))
            cq_assembly.add(part, color=cq.Color(*part_ref.color), name=part_ref.name, loc=loc)
        return cq_assembly


    @staticmethod
    def load_project(proj_path: Union[Path, str]):
        inventory = Inventory()
        assembly_index = AssemblyIndex()
        assemblies = CadService.read_assemblies(proj_path, inventory)
        cq_assembly = CadService.cq_reassemble(assemblies, inventory, assembly_index)
        assembly_index.prev_inventory = inventory
        return Project(inventory=inventory, assemblies=assemblies, cq_assembly=cq_assembly, assembly_index=assembly_index)

    @staticmethod
    def visualize_project(proj_path: Union[Path, str], html_path: Union[Path, str, None] = None):
        proj_path = Path(proj_path)
        if html_path is None:
            html_path = proj_path / "index.html"
        project = CadService.load_project(proj_path)
        show(project.cq_assembly)

    @staticmethod
    def get_part_checksum(solid: cq.Solid, precision=3):
        vertices = np.array([v.toTuple() for v in solid.vertices()])

        rounded_tri_vertices = np.round(vertices, precision)

        sorted_indices = np.lexsort(rounded_tri_vertices.T) 
        sorted_tri_vertices = rounded_tri_vertices[sorted_indices] 

        vertices_hash = hashlib.md5(sorted_tri_vertices.tobytes()).digest()
        return hashlib.md5(vertices_hash).hexdigest()




# recreated_original_solid = CadHelper.transform_solid(assembly_index.part_index_to_part[part_index], rotmat).translate(offset.tolist())
# recreated_original_solid_checksum = CadHelper.get_part_checksum(recreated_original_solid)
# original_solid_checksum = CadHelper.get_part_checksum(aligned_part)
# assert recreated_original_solid_checksum == original_solid_checksum, f"recreated_original_solid_checksum: {recreated_original_solid_checksum} != original_solid_checksum: {original_solid_checksum}"


