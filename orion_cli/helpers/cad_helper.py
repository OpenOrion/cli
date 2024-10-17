import hashlib
from io import BytesIO
from pathlib import Path
import pickle
from typing import Iterable, Optional, Union, cast
from cachetools import LRUCache, cached
import numpy as np
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS_Shape, TopoDS_Vertex
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepTools import BRepTools
from OCP.BRep import BRep_Builder, BRep_Tool
import cadquery as cq
from OCP.BRepGProp import BRepGProp
import cadquery as cq
from ocp_tessellate.stepreader import StepReader
from orion_cli.helpers.file_helper import FileHelper
from jupyter_cadquery.tessellator import save_cache, get_shape_checksum

RotationMatrixLike = Union[np.ndarray, list[list[float]]]
VectorLike = Union[np.ndarray, list[float]]


class CadHelper:
    get_shape_checksum = staticmethod(get_shape_checksum)
    @staticmethod
    def rgba_int_to_float(rgb_int: Iterable[float]):
        """
        Convert an integer-based RGB tuple (0-255) to a float-based RGB tuple (0.0-1.0). Alpha value is not converted.

        Args:
        rgb_int (tuple): A tuple of three integers representing RGB values.

        Returns:
        tuple: A tuple of three floats representing RGB values.
        """
        return tuple([x / 255.0 if i < 3 else x for i, x in enumerate(rgb_int)])

    @staticmethod
    def rgba_float_to_int(rgb_float: Iterable[float]):
        """
        Convert a float-based RGB tuple (0.0-1.0) to an integer-based RGB tuple (0-255). Alpha value is not converted.

        Args:
        rgb_float (tuple): A tuple of three floats representing RGB values.

        Returns:
        tuple: A tuple of three integers representing RGB values.
        """
        return tuple(
            [float(int(x * 255)) if i < 3 else x for i, x in enumerate(rgb_float)]
        )

    @staticmethod
    def vertex_to_Tuple(vertex: TopoDS_Vertex):
        geom_point = BRep_Tool.Pnt_s(vertex)
        return (geom_point.X(), geom_point.Y(), geom_point.Z())

    @staticmethod
    def transform_solid(
        solid: cq.Solid, rotmat: RotationMatrixLike, offset: Optional[VectorLike] = None
    ):
        if offset is None:
            offset = np.zeros(3)

        # Get the transformation
        loc = CadHelper.get_location(rotmat, offset)
        transformation = loc.wrapped.Transformation()

        # Apply the transformation
        transformer = BRepBuilderAPI_Transform(solid.wrapped, transformation, False)
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
        return cq.Solid(shape)

    @staticmethod
    def import_step(file_path: Union[Path, str]) -> cq.Assembly:
        """
        Import a STEP file
        Returns a TopoDS_Shape object
        """
        file_path = Path(file_path)
        assert file_path.exists(), f"File not found: {file_path}"
        assert file_path.suffix.lower() in [".step", ".stp"], "Invalid file type"

        r = StepReader()
        r.load(str(file_path))
        return cast(cq.Assembly, r.to_cadquery())

    @staticmethod
    def import_cad(file_path: Union[Path, str]) -> cq.Assembly:
        """
        Import a CAD file
        Returns a TopoDS_Shape object
        """
        file_path = Path(file_path)

        is_plaintext = FileHelper.is_plaintext(file_path)

        if is_plaintext and file_path.suffix.lower() in [".step", ".stp"]:
            return CadHelper.import_step(file_path)

        raise ValueError("Invalid CAD file type")

    @staticmethod
    def export_brep(shape: TopoDS_Shape, file_path: str):
        BRepTools.Write_s(shape, file_path)

    @staticmethod
    def normalize_part(solid: cq.Solid, norm_axis: bool = False):
        offset = np.array(solid.Center().toTuple())
        centered_solid = solid.translate((-offset).tolist())

        curr_solid = centered_solid
        rotmat_axis_of_inertia = np.eye(3)

        if norm_axis:
            for axis_index in range(2):
                axis_vector = np.zeros(3)
                axis_vector[axis_index] = 1

                Properties = GProp_GProps()
                BRepGProp.VolumeProperties_s(curr_solid.wrapped, Properties)
                principle_properties = Properties.PrincipalProperties()

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
    def align_vertices(vertices1, vertices2):
        """
        Align vertices2 to vertices1 using Procrustes analysis.

        Parameters:
        vertices1 (numpy.ndarray): Vertices of the first solid (N x 3).
        vertices2 (numpy.ndarray): Vertices of the second solid (N x 3).

        Returns:
        aligned_vertices2 (numpy.ndarray): Rotated vertices2 aligned with vertices1.
        rotation_matrix (numpy.ndarray): Rotation matrix applied to vertices2.
        """
        # Center the vertices to the origin
        centroid1 = np.mean(vertices1, axis=0)
        centroid2 = np.mean(vertices2, axis=0)
        vertices1_centered = vertices1 - centroid1
        vertices2_centered = vertices2 - centroid2

        # Compute covariance matrix
        H = np.dot(vertices2_centered.T, vertices1_centered)

        # Singular Value Decomposition (SVD)
        U, S, Vt = np.linalg.svd(H)
        rotation_matrix = np.dot(Vt.T, U.T)

        return rotation_matrix

    @staticmethod
    def align_parts(part1: cq.Solid, part2: cq.Solid):
        vertices1 = np.array([vertex.toTuple() for vertex in part1.Vertices()])
        vertices2 = np.array([vertex.toTuple() for vertex in part2.Vertices()])

        assert len(vertices1) == len(vertices2), "solid1 and solid2 are different"

        rotmat = CadHelper.align_vertices(vertices2, vertices1)
        aligned_vertices2 = np.dot(vertices2, rotmat)
        error = np.sum(np.sum(vertices1 - aligned_vertices2, axis=0))
        if error < 1e-3:
            return rotmat

        raise ValueError(f"failed to align, error: {error}")

    @staticmethod
    def get_viewer(
        cad_obj, cache_path: Union[Path, str, None] = None, remote_viewer: bool = False
    ):
        if remote_viewer:
            from jupyter_cadquery.viewer import show
        else:
            from jupyter_cadquery import show
        from jupyter_cadquery.tessellator import create_cache
    
        if cache_path and Path(cache_path).exists():
            with open(cache_path, "rb") as f:
                cache = pickle.load(f)
        else:
            cache = create_cache()
            # print(tess.cache)
        viewer = show(cad_obj, cache=cache, viewer=None)

        if cache_path:
            save_cache(cache, cache_path)
        return viewer

    @staticmethod
    def assert_correctly_aligned(
        base_part: cq.Solid,
        aligned_part: cq.Solid,
        rotmat: RotationMatrixLike,
        offset: VectorLike,
    ):
        recreated_original_solid = CadHelper.transform_solid(
            base_part, rotmat
        ).translate(offset.tolist())
        recreated_original_solid_checksum = CadHelper.get_part_checksum(
            recreated_original_solid
        )
        original_solid_checksum = CadHelper.get_part_checksum(aligned_part)
        assert (
            recreated_original_solid_checksum == original_solid_checksum
        ), f"recreated_original_solid_checksum: {recreated_original_solid_checksum} != original_solid_checksum: {original_solid_checksum}"


