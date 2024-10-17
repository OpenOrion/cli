from typing import Optional, Union
from pydantic import BaseModel, ConfigDict, Field
import uuid
from orion_cli.helpers.cad_helper import CadHelper
from orion_cli.utils.numpy import NdArray
from OCP.gp import gp_Trsf
import numpy as np
import cadquery as cq

AssemblyPath = str
AssemblyId = str
PartChecksum = str

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
            orientation=self.orientation.dot(location.orientation),
        )

    @staticmethod
    def convert(loc: Union["Location", cq.Location, None]):
        if loc is None:
            return Location(position=np.zeros(3), orientation=np.eye(3))
        if isinstance(loc, Location):
            return loc

        transformation = loc.wrapped.Transformation()
        translation = np.array(
            [
                transformation.Value(1, 4),
                transformation.Value(2, 4),
                transformation.Value(3, 4),
            ]
        )
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

        return Location(position=translation, orientation=rotmat)


class PartVariationRef(BaseModel):
    checksum: PartChecksum
    id: int

    def __hash__(self):
        return hash((self.checksum, self.id))

class AssemblyLike(BaseModel):
    path: AssemblyPath = Field(exclude=True, default=None)
    location: Optional[Location] = None
    id: AssemblyId = Field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def parent_path(self):
        path_names = self.path.split("/")
        assert len(path_names) > 0, "Invalid path"
        return "/".join(path_names[:-1]) or "/"

    @property
    def name(self):
        path_names = self.path.split("/")
        assert len(path_names) > 0, "Invalid path"
        return path_names[-1]

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

    children: list[AssemblyId] = Field(default_factory=list)
    parts: list[PartRef] = Field(default_factory=list)
