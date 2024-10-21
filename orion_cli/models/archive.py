from typing import Any, Literal, Optional, OrderedDict, Union
import uuid
from pydantic import BaseModel, ConfigDict, Field
import cadquery as cq

from orion_cli.models.assembly import (
    Assembly,
    PartRef,
    AssemblyId,
    AssemblyPath,
    PartVariationRef,
    PartChecksum,
)

PartSurfaceArea = float
PartNumVertices = int
PartGroup = tuple[PartSurfaceArea, PartNumVertices]
AlignedPartChecksum = str
PartName = str


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

    def get_variation(self, ref: PartVariationRef):
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


class ArchiveIndex(BaseModel):
    """
    Index is for caching operations and revisioning for changes to the assembly
    """

    # caching
    base_parts: dict[PartGroup, cq.Solid] = Field(default_factory=dict)
    aligned_refs: dict[AlignedPartChecksum, PartRef] = Field(default_factory=dict)
    part_names: dict[PartName, Optional[PartRef]] = Field(default_factory=dict)

    # revisioning
    prev_archive: Optional["CadArchive"] = None
    is_part_modified: set[PartVariationRef] = Field(default_factory=set)
    is_assembly_modified: set[AssemblyId] = Field(default_factory=set)

    model_config = ConfigDict(arbitrary_types_allowed=True)
    paths: OrderedDict[AssemblyPath, AssemblyId] = Field(default_factory=OrderedDict)

class CadArchive(BaseModel):
    root_assembly_id: Optional[AssemblyId] = None
    assemblies: OrderedDict[AssemblyId, Assembly] = Field(default_factory=OrderedDict)
    part_refs: OrderedDict[AssemblyId, PartRef] = Field(default_factory=OrderedDict)
    inventory: Inventory = Field(default_factory=Inventory)
    config: ArchiveConfig = Field(default_factory=ArchiveConfig)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    index: ArchiveIndex = Field(default_factory=ArchiveIndex, exclude=True)

    def __init__(self, **data: Any):
        super().__init__(**data)
        if len(self.assemblies) > 0:
            self.init_assembly(self.root_assembly)

    def init_assembly(self, assembly: Assembly, parent_path: Optional[AssemblyPath] = None):
        self.add_assembly(assembly, parent_path or "")
        for part_id in assembly.parts:
            self.add_part_ref(self.part_refs[part_id], assembly)
        for child_id in assembly.children:
            self.init_assembly(self.assemblies[child_id], assembly.path)

    def add_part_ref(self, part_ref: PartRef, assembly: Assembly, name: str = None):
        name = name or part_ref.name
        assert name, "Part name is required"
        new_part_ref_path = f"{assembly.path}/{part_ref.name}"
        assert (
            new_part_ref_path not in self.index.paths
        ), f"Path '{new_part_ref_path}' already exists"
        part_ref.path = new_part_ref_path
        assembly.parts.add(part_ref.id)
        self.part_refs[part_ref.id] = part_ref
        self.index.paths[part_ref.path] = part_ref.id

    @property
    def root_assembly(self):
        return self.get_assembly(self.root_assembly_id)

    def add_assembly(
        self, assembly: Assembly, parent: Union[Assembly, AssemblyPath, None] = None
    ):
        if not parent and not self.root_assembly_id:
            self.root_assembly_id = assembly.id

        parent_assembly = None
        if isinstance(parent, Assembly):
            parent_path = parent.path
            parent_assembly = parent
        elif isinstance(parent, AssemblyPath):
            parent_path = parent
            parent_assembly = self.get_by_path(parent_path, "assembly")
        else:
            parent_path = ""

        new_assembly_path = f"{parent_path}/{assembly.name}"
        assert (
            new_assembly_path not in self.index.paths
        ), f"Path '{new_assembly_path}' already exists"
        assembly.path = new_assembly_path

        if parent_assembly:
            parent_assembly.children.add(assembly.id)

        self.update_assembly_path(assembly, new_assembly_path)
        self.assemblies[assembly.id] = assembly
        self.index.paths[assembly.path] = assembly.id

    def update_assembly_path(self, assembly: Assembly, new_path: str):
        # Update child paths
        if assembly.path and assembly.path != new_path:
            for path in self.index.paths:
                if path.startswith(assembly.path):
                    self.index.paths[path.replace(assembly.path, new_path, 1)] = self.index.paths[
                        path
                    ]
                    del self.index.paths[path]
        assembly.path = new_path

    @staticmethod
    def remove_assembly(self, assembly_id: AssemblyId):
        assert assembly_id in self.assemblies, f"Assembly '{assembly_id}' not found"

        assembly = self.get_assembly(assembly_id)
        assert assembly.path in self.paths, f"Assembly '{assembly.path}' not found"
        parent_assembly = self.get_by_path(assembly.parent_path, "assembly")

        assert isinstance(
            parent_assembly, Assembly
        ), f"Assembly {assembly.parent_path} not an assembly "

        parent_assembly.children.remove(assembly_id)
        del self.assemblies[assembly_id]
        del self.paths[assembly.path]

    @staticmethod
    def remove_part_ref(self, part_ref_id: AssemblyId):
        part_ref = self.part_refs[part_ref_id]
        parent_assembly = self.get_by_path(part_ref.parent_path, "assembly")
        assert isinstance(
            parent_assembly, Assembly
        ), f"{part_ref.parent_path} is a part not assembly"

        assert (
            part_ref_id in self.part_refs
        ), f"Part reference '{part_ref_id}' not found"
        assert (
            part_ref.path in self.paths
        ), f"Part reference '{part_ref.path}' not found"

        parent_assembly.parts.remove(part_ref_id)
        del self.part_refs[part_ref_id]
        del self.paths[part_ref.path]

    def get_assembly(self, assembly_id: AssemblyId):
        if assembly_id in self.assemblies:
            return self.assemblies[assembly_id]

    def get_by_path(
        self, path: AssemblyPath, type: Literal["assembly", "part"] = "assembly"
    ):
        if path in self.index.paths:
            assembly_id = self.index.paths[path]

            assert (
                assembly_id in self.assemblies
                if type == "assembly"
                else assembly_id in self.part_refs
            ), f"{assembly_id} does is not {type}"

            return (
                self.assemblies[assembly_id]
                if type == "assembly"
                else self.part_refs[assembly_id]
            )

    def model_copy(self, *, update: dict[str, Any] | None = None, deep: bool = False):
        part_refs = OrderedDict[AssemblyId, PartRef]()
        assemblies = OrderedDict[AssemblyId, Assembly]()
        for k, v in self.assemblies.items():
            assemblies[k] = v.model_copy(update=update, deep=deep)
        for k, v in self.part_refs.items():
            part_refs[k] = v.model_copy(update=update, deep=deep)

        return CadArchive(
            assemblies=assemblies,
            part_refs=part_refs,
            inventory=self.inventory.model_copy(update=update, deep=deep),
            config=self.config.model_copy(update=update, deep=deep),
        )
