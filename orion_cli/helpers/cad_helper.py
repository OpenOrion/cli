from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Optional, Union
import numpy as np
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS_Shape, TopoDS_Vertex, TopoDS
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf
from OCP.BRepTools import BRepTools
from OCP.BRep import BRep_Builder, BRep_Tool
import cadquery as cq
from OCP.BRepGProp import BRepGProp
from scipy.spatial.transform import Rotation as R
from ocp_tessellate.tessellator import Tessellator, compute_quality
from ocp_tessellate.ocp_utils import bounding_box, get_location
import cadquery as cq



@dataclass
class Mesh:
    vertices: np.ndarray
    simplices: np.ndarray
    normals: np.ndarray
    edges: np.ndarray


class CadHelper:
    @staticmethod
    def vertex_to_Tuple(vertex: TopoDS_Vertex):
        geom_point = BRep_Tool.Pnt_s(vertex)
        return (geom_point.X(), geom_point.Y(), geom_point.Z())

    @staticmethod
    def tesselate_shape(shape: cq.Solid):
        tess = Tessellator("")

        bb = bounding_box(shape.wrapped, loc=get_location(None), optimal=False)
        quality = compute_quality(bb, deviation=0.1)

        tess.compute(
            shape.wrapped,
            quality,
            angular_tolerance=0.2,
            compute_faces=True,
            compute_edges=True,
            debug=False,
        )
        tri_vertices = tess.get_vertices().reshape(-1, 3)
        tri_indices = tess.get_triangles().reshape(-1, 3)
        tri_normals = tess.get_normals().reshape(-1, 3)
        edges = tess.get_edges().reshape(-1, 2, 3)
        return Mesh(
            vertices=tri_vertices,
            simplices=tri_indices,
            normals=tri_normals,
            edges=edges,
        )

    def transform_solid(
        solid: cq.Solid, orientation: np.ndarray, offset: Optional[np.ndarray] = None
    ):
        if offset is None:
            offset = np.zeros(3)
        # Create a transformation object
        transformation = gp_Trsf()
        transformation.SetValues(
            orientation[0][0],
            orientation[0][1],
            orientation[0][2],
            offset[0],
            orientation[1][0],
            orientation[1][1],
            orientation[1][2],
            offset[1],
            orientation[2][0],
            orientation[2][1],
            orientation[2][2],
            offset[2],
        )

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
                principle_properties.ThirdAxisOfInertia(),
            )

            axis_of_inertias = np.array(
                [
                    (
                        axis_of_inertias_occ[0].X(),
                        axis_of_inertias_occ[0].Y(),
                        axis_of_inertias_occ[0].Z(),
                    ),
                    (
                        axis_of_inertias_occ[1].X(),
                        axis_of_inertias_occ[1].Y(),
                        axis_of_inertias_occ[1].Z(),
                    ),
                    (
                        axis_of_inertias_occ[2].X(),
                        axis_of_inertias_occ[2].Y(),
                        axis_of_inertias_occ[2].Z(),
                    ),
                ]
            )

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
            curr_solid = CadHelper.transform_solid(curr_solid, axis_of_inertias)
        rotmat = rotmat_axis_of_inertia.T
        return curr_solid, offset, rotmat

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
        if error < 1e-3:
            return rotmat

        raise ValueError("failed to align parts")



    @staticmethod
    def get_part_checksum(solid: cq.Solid, precision=3):

        vertices = np.array(
            [CadHelper.vertex_to_Tuple(TopoDS.Vertex_s(v)) for v in solid._entities("Vertex")]
        )

        rounded_tri_vertices = np.round(vertices, precision)

        sorted_indices = np.lexsort(rounded_tri_vertices.T)
        sorted_tri_vertices = rounded_tri_vertices[sorted_indices]

        vertices_hash = hashlib.md5(sorted_tri_vertices.tobytes()).digest()
        return hashlib.md5(vertices_hash).hexdigest()



# recreated_original_solid = CadHelper.transform_solid(index.part_index_to_part[part_index], rotmat).translate(offset.tolist())
# recreated_original_solid_checksum = CadHelper.get_part_checksum(recreated_original_solid)
# original_solid_checksum = CadHelper.get_part_checksum(aligned_part)
# assert recreated_original_solid_checksum == original_solid_checksum, f"recreated_original_solid_checksum: {recreated_original_solid_checksum} != original_solid_checksum: {original_solid_checksum}"