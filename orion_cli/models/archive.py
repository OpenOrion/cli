from typing import Any, Literal, Optional, OrderedDict
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


class CadArchive(BaseModel):
    assemblies: OrderedDict[AssemblyId, Assembly] = Field(default_factory=OrderedDict)
    part_refs: OrderedDict[AssemblyId, PartRef] = Field(default_factory=OrderedDict)
    paths: OrderedDict[AssemblyPath, tuple[Literal["assembly", "part"], AssemblyId]] = (
        Field(default_factory=OrderedDict)
    )
    inventory: Inventory = Field(default_factory=Inventory)
    config: ArchiveConfig = Field(default_factory=ArchiveConfig)

    index: ArchiveIndex = Field(default_factory=ArchiveIndex, exclude=True)

    def get_assembly(self, assembly_id: AssemblyId):
        assert assembly_id in self.assemblies, f"Assembly {assembly_id} not found"
        return self.assemblies[assembly_id]

    def get_by_path(self, path: AssemblyPath):
        assert path in self.paths, f"Assembly {path} not found"
        assembly_type, assembly_id = self.paths[path]
        return (
            self.assemblies[assembly_id]
            if assembly_type == "assembly"
            else self.part_refs[assembly_id]
        )

    @property
    def root_assembly(self):
        return next(iter(self.assemblies.values()))

    def model_copy(self, *, update: dict[str, Any] | None = None, deep: bool = False):
        part_refs = OrderedDict[AssemblyId, PartRef]()
        assemblies = OrderedDict[AssemblyId, Assembly]()
        for k, v in self.assemblies.items():
            assemblies[k] = v.model_copy(update=update, deep=deep)
            for part in v.parts:
                part_refs[part.id] = part

        return CadArchive(
            assemblies=assemblies,
            part_refs=part_refs,
            inventory=self.inventory.model_copy(update=update, deep=deep),
            config=self.config.model_copy(update=update, deep=deep),
            paths=self.paths.copy(),
        )