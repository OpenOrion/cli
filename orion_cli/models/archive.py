# Parameter Labels
from typing import Any, Optional, OrderedDict, Union
import uuid
from pydantic import BaseModel, ConfigDict, Field
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

    def get_variation(self, ref: InventoryVariationRef):
        return self.catalog.items[ref.checksum].variations[ref.id - 1]

    def get_variation_from_color(
        self,
        part_checksum: PartChecksum,
        part_color: Optional[list[float]] = None,
    ):
        if part_checksum in self.catalog.items:
            for variation in self.catalog.items[part_checksum].variations:
                if variation.color == part_color:
                    return variation

    def find_variation_id(
        self, part_checksum: PartChecksum, part_color: Optional[list[float]] = None
    ):
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
        archive.remove_assembly(child_id)

    def remove_part_ref(self, part_ref_id: AssemblyId, archive: "CadArchive"):
        archive.remove_part_ref(part_ref_id)
        for i, part_ref in enumerate(self.parts):
            if part_ref.id == part_ref_id:
                del self.parts[i]
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
        archive.add_assembly(child)
        # archive.update_paths(self.path, child.children, is_assembly=True)

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
        archive.add_part_ref(part_ref)

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


class ArchiveIndex(BaseModel):
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


class CadArchive(BaseModel):
    assemblies: OrderedDict[AssemblyId, Assembly] = Field(default_factory=OrderedDict)
    part_refs: OrderedDict[AssemblyId, PartRef] = Field(default_factory=OrderedDict)
    inventory: Inventory = Field(default_factory=Inventory)
    config: ArchiveConfig = Field(default_factory=ArchiveConfig)
    paths: OrderedDict[AssemblyPath, Union[Assembly, PartRef]] = Field(
        default_factory=OrderedDict
    )
    index: ArchiveIndex = Field(default_factory=ArchiveIndex, exclude=True)

    def add_assembly(self, assembly: Assembly):
        self.assemblies[assembly.id] = assembly
        self.paths[assembly.path] = assembly

    def add_part_ref(self, part_ref: PartRef):
        self.part_refs[part_ref.id] = part_ref
        self.paths[part_ref.path] = part_ref

    def remove_assembly(self, assembly_id: AssemblyId):
        assert assembly_id in self.assemblies, "Assembly not found"
        del self.assemblies[assembly_id]

    def remove_part_ref(self, part_ref_id: AssemblyId):
        assert part_ref_id in self.part_refs, "Part not found"
        del self.part_refs[part_ref_id]

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

    # TODO: make sure this is correct
    def update_paths(
        self,
        parent_path: AssemblyPath,
        children: list[AssemblyId],
        is_assembly: bool = True,
    ):
        for child_id in children:
            child = (
                self.assemblies.get(child_id)
                if is_assembly
                else self.part_refs.get(child_id)
            )
            if child:
                child.path = f"{parent_path}/{child.name}"
                self.paths[child.path] = child
                self.update_paths(child.path, child.children)

    def get_by_path(self, path: AssemblyPath):
        assert path and path in self.paths, f"Assembly not found: {path}"
        assembly = self.paths[path]
        assert isinstance(assembly, Assembly), f"Not an Assembly: {path}"
        return assembly
