from typing import Optional, Union
from pydantic import BaseModel, ConfigDict, Field
import uuid
from orion_cli.utils.numpy import NdArray
from OCP.gp import gp_Trsf
import numpy as np
import cadquery as cq
from scipy.spatial.transform import Rotation as R
from orion_cli.utils.ordered_set import OrderedSet, OrderedSetAnnotated

AssemblyPath = str
AssemblyId = str
PartChecksum = str




class Location(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    position: NdArray  # Assuming position is a 1D array with 3 elements
    orientation: NdArray  # Quaternion as [x, y, z, w]

    def to_cq(self):
        # Convert quaternion to rotation matrix
        rotation = R.from_quat(self.orientation).as_matrix()

        # Create the transformation using the position and the rotation matrix
        transformation = gp_Trsf()
        transformation.SetValues(
            rotation[0][0], rotation[0][1], rotation[0][2], self.position[0],
            rotation[1][0], rotation[1][1], rotation[1][2], self.position[1],
            rotation[2][0], rotation[2][1], rotation[2][2], self.position[2],
        )
        return cq.Location(transformation)

    @property
    def is_zero(self):
        return np.all(self.position == 0) and np.all(self.orientation == np.array([0, 0, 0, 1]))

    def transform(self, location: Union["Location", cq.Location, None]):
        if location is None:
            return self.model_copy()

        if isinstance(location, cq.Location):
            location = Location.convert(location)

        # Add positions
        new_position = self.position + location.position

        # Multiply quaternions to combine orientations
        new_orientation = R.from_quat(self.orientation) * R.from_quat(location.orientation)

        return Location(
            position=new_position,
            orientation=new_orientation.as_quat()
        )

    @staticmethod
    def convert(loc: Union["Location", cq.Location, None]):
        if loc is None:
            return Location(position=np.zeros(3), orientation=np.array([0, 0, 0, 1]))
        if isinstance(loc, Location):
            return loc

        # Extract the translation from the cadquery Location object
        transformation = loc.wrapped.Transformation()
        translation = np.array(
            [
                transformation.Value(1, 4),
                transformation.Value(2, 4),
                transformation.Value(3, 4),
            ]
        )

        # Extract rotation matrix and convert to quaternion
        rotmat = np.array(
            [
                [
                    transformation.Value(1, 1),
                    transformation.Value(1, 2),
                    transformation.Value(1, 3),
                ],
                [
                    transformation.Value(2, 1),
                    transformation.Value(2, 2),
                    transformation.Value(2, 3),
                ],
                [
                    transformation.Value(3, 1),
                    transformation.Value(3, 2),
                    transformation.Value(3, 3),
                ],
            ]
        )

        # Convert rotation matrix to quaternion
        quaternion = R.from_matrix(rotmat).as_quat()

        return Location(position=translation, orientation=quaternion)


class PartVariationRef(BaseModel):
    checksum: PartChecksum
    id: int

    def __hash__(self):
        return hash((self.checksum, self.id))


class AssemblyLike(BaseModel):
    path: AssemblyPath = Field(exclude=True, default=None)
    location: Optional[Location] = None
    id: AssemblyId = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str

    @property
    def parent_path(self):
        path_names = self.path.split("/")
        assert len(path_names) > 0, "Invalid path"
        return "/".join(path_names[:-1]) or "/"

    @property
    def long_name(self):
        return self.path.lstrip("/").replace("/", "-") if self.path else ""


class PartRef(AssemblyLike):
    """
    Reference to a part in the inventory with a specific position and orientation (rotation matrix)
    """

    variation: PartVariationRef


class Assembly(AssemblyLike):
    """
    Assembly of parts and subassemblies as references
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    children: OrderedSetAnnotated[AssemblyId] = Field(default_factory=OrderedSet)
    parts: OrderedSetAnnotated[AssemblyId] = Field(default_factory=OrderedSet)

    def set_exclude_fields(self, exclude: bool):
        self.model_fields["children"].exclude = exclude
        self.model_fields["parts"].exclude = exclude
