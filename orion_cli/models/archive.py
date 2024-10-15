# Parameter Labels
from dataclasses import Field
from typing import Any, Optional, OrderedDict, Union
import uuid
from pydantic import BaseModel, ConfigDict
import cadquery as cq
from orion_cli.helpers.cad_helper import CadHelper
from orion_cli.utils.numpy import NdArray
from OCP.gp import gp_Trsf
import numpy as np

PartSurfaceArea = float
PartNumVertices = int
PartGroup = tuple[PartSurfaceArea, PartNumVertices]
PartChecksum = str
AlignedPartChecksum = str
PartName = str
AssemblyPath = str
AssemblyId = str


class ArchiveConfig(BaseModel):
    name: str
    max_name_depth: int = 3
    normalize_axis: bool = False
    use_part_references: bool = True
    include_assets: bool = False


class InvetoryPartVariationMetadata(BaseModel):
    price: Optional[float] = None
    url: Optional[str] = None


class InventoryPartVariation(BaseModel):
    id: int
    references: list[AssemblyId] = Field(default_factory=list)
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


class Inventory(BaseModel):
    """
    Catalog of all parts in the project
    """

    parts: dict[PartChecksum, cq.Solid] = Field(default_factory=dict, exclude=True)
    catalog: InventoryCatalog = Field(default_factory=InventoryCatalog)
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def model_copy(self, *, update: dict[str, Any] | None = None, deep: bool = False):
        cloned_parts = {checksum: part for checksum, part in self.parts.items()}
        return Inventory(
            parts=cloned_parts,
            catalog=self.catalog.model_copy(update=update, deep=deep),
        )


class Location(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    position: NdArray
    orientation: NdArray

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


class PartRef(BaseModel):
    """
    Reference to a part in the inventory with a specific position and orientation (rotation matrix)
    """

    path: AssemblyPath = Field(exclude=True, default=None)
    name: str
    variation: InventoryVariationRef
    id: AssemblyId = Field(default_factory=lambda: str(uuid.uuid4()))
    location: Optional[Location] = None


class Assembly(BaseModel):
    """
    Assembly of parts and subassemblies as references
    """
    path: Optional[AssemblyPath] = Field(default=None, exclude=True)
    id: AssemblyId = Field(default_factory=lambda: str(uuid.uuid4()))
    location: Optional[Location] = None
    children: list[AssemblyId] = Field(default_factory=list)
    parts: list[PartRef] = Field(default_factory=list)

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

    def remove_child(self, child_id: AssemblyId, archive: "CadArchive"):
        assert child_id in self.children, "Child not found"
        self.children.remove(child_id)
        del archive.assemblies[child_id]

    def remove_part_ref(self, part_ref_id: AssemblyId, archive: "CadArchive"):
        for i, part_ref in enumerate(self.parts):
            if part_ref.id == part_ref_id:
                del self.parts[i]
                del archive.part_refs[part_ref_id]
                break

    def add_child(
        self,
        child: "Assembly",
        archive: "CadArchive",
        name: Optional[str] = None,
    ):
        child_name = name or child.name
        child.path = f"{self.path}/{child_name}"
        if not child_name:
            raise ValueError("Invalid new name")
        assert child.id not in self.children, "Child already exists"
        self.children.append(child.id)
        archive.assemblies[child.id] = child
        archive.paths[child.path] = child

    def add_part_ref(
        self,
        part_ref: PartRef,
        archive: "CadArchive",
        name: Optional[str] = None,
    ):
        child_name = name or part_ref.name
        part_ref.path = f"{self.path}/{child_name}"
        if not child_name:
            raise ValueError("Invalid new name")
        self.parts.append(part_ref)
        archive.part_refs[part_ref.id] = part_ref
        archive.paths[part_ref.path] = part_ref

    def to_cq(
        self,
        archive: "CadArchive",
        abs_location: Optional[Location] = None,
    ):
        cq_assembly = cq.Assembly(name=self.name)
        for subassembly_id in self.children:
            subassembly = archive.assemblies[subassembly_id]
            asm_abs_location = Location.convert(subassembly.location).transform(
                abs_location
            )
            cq_assembly.add(
                subassembly.to_cq(archive),
                loc=asm_abs_location.to_cq(),
                name=subassembly.name,
            )
        for part_ref in self.parts:
            part = archive.inventory.parts[part_ref.variation.checksum]
            cq_loc = part_ref.location and part_ref.location.to_cq()
            part_variation = archive.inventory.get_variation(part_ref.variation)

            # TODO: find a better solution to handle negative rotation determinants (mirrors)
            cq_color = (
                cq.Color(*CadHelper.rgba_int_to_float(part_variation.color))
                if part_variation.color
                else None
            )
            if cq_loc and cq_loc.wrapped.Transformation().IsNegative():
                part_abs_location = Location.convert(part_ref.location).transform(
                    abs_location
                )
                aligned_part = CadHelper.transform_solid(
                    part, part_abs_location.orientation, part_abs_location.position
                )
                cq_assembly.add(aligned_part, color=cq_color, name=part_ref.name)
            else:
                cq_assembly.add(part, color=cq_color, name=part_ref.name, loc=cq_loc)

        return cq_assembly

    @staticmethod
    def get_by_path(archive: "CadArchive", path: AssemblyPath):
        assert path and path in archive.paths, f"Assembly not found: {path}"
        assembly = archive.paths[path]
        assert isinstance(assembly, Assembly), f"Not an Assembly: {path}"
        return assembly


class CadArchive(BaseModel):
    assemblies: OrderedDict[AssemblyId, Assembly] = Field(default_factory=OrderedDict)
    part_refs: OrderedDict[AssemblyId, PartRef] = Field(default_factory=OrderedDict)
    inventory: Inventory = Field(default_factory=Inventory)
    config: ArchiveConfig = Field(default_factory=ArchiveConfig)
    paths: OrderedDict[AssemblyPath, Union[Assembly, PartRef]] = Field(
        default_factory=OrderedDict
    )

    @property
    def root_assembly(self):
        return next(iter(self.assemblies.values()))

    def model_copy(self, *, update: dict[str, Any] | None = None, deep: bool = False):
        part_refs = OrderedDict[AssemblyId, PartRef]()
        assemblies = OrderedDict[AssemblyId, Assembly]()
        paths = OrderedDict[AssemblyPath, Union[Assembly, PartRef]]()
        for k, v in self.assemblies.items():
            assemblies[k] = v.model_copy(update=update, deep=deep)
            paths[v.path] = assemblies[k]
            for part in v.parts:
                part_refs[part.id] = part
                paths[part.path] = part
        return CadArchive(
            assemblies=assemblies,
            part_refs=part_refs,
            inventory=self.inventory.model_copy(update=update, deep=deep),
            config=self.config.model_copy(update=update, deep=deep),
            paths=paths,
        )


class AssemblyIndex(BaseModel):
    """
    Index is for caching operations and revisioning for changes to the assembly
    """

    # caching
    base_parts: dict[PartGroup, cq.Solid] = Field(default_factory=dict)
    aligned_refs: dict[AlignedPartChecksum, PartRef] = Field(default_factory=dict)
    part_names: dict[PartName, Optional[PartRef]] = Field(default_factory=dict)
    part_colors: dict[PartChecksum, set[tuple[float]]] = Field(default_factory=dict)

    # revisioning
    prev_archive: Optional["CadArchive"] = None
    is_part_modified: set[InventoryVariationRef] = Field(default_factory=set)
    is_assembly_modified: set[AssemblyId] = Field(default_factory=set)

    model_config = ConfigDict(arbitrary_types_allowed=True)
