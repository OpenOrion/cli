from typing import Optional, Sized, cast
import numpy as np
import cadquery as cq
import cadquery as cq
from orion_cli.models.archive import (
    ArchiveConfig,
    Assembly,
    ArchiveIndex,
    CadArchive,
    CatalogItem,
    Inventory,
    InventoryPartVariation,
    InventoryVariationRef,
    Location,
    PartRef,
)
from orion_cli.helpers.cad_helper import CadHelper


class ArchiveHelper:
    @staticmethod
    def process_assembly(
        cq_assembly: cq.Assembly,
        archive: Optional[CadArchive] = None,
        curr_abs_location: Optional[Location] = None,
        curr_path: str = "",
    ):
        # initialize archive and index if not provided
        if archive is None:
            archive = CadArchive()

        # convert location to absolute location
        rel_location = Location.convert(cq_assembly.loc)
        abs_location = rel_location.transform(curr_abs_location)

        root_assembly = Assembly(
            path=curr_path + f"/{cq_assembly.name}",
            location=rel_location if not rel_location.is_zero else None,
        )
        assemblies = [root_assembly]

        if curr_path == "":
            archive.index.is_assembly_modified.clear()
            archive.index.is_part_modified.clear()
            archive.add_assembly(root_assembly)

        is_modified = False
        for cq_subassembly in cq_assembly.children:
            if isinstance(cq_subassembly, cq.Assembly) and len(cq_subassembly.children):
                subassemblies, is_sub_modified = ArchiveHelper.process_assembly(
                    cq_subassembly,
                    archive,
                    abs_location,
                    root_assembly.path,
                )
                root_assembly.add_child(subassemblies[0], archive)
                assemblies.extend(subassemblies)

                is_modified = is_modified or is_sub_modified
                if is_modified:
                    archive.index.is_assembly_modified.add(root_assembly.id)
            else:
                base_part, part_ref = ArchiveHelper.get_part(
                    cq_subassembly,
                    root_assembly.path,
                    abs_location,
                    archive.inventory,
                    archive.index,
                    archive.config,
                )

                is_modified = not (
                    # has the part id been previously indexed
                    archive.index.prev_archive
                    and part_ref.path in archive.index.prev_archive.paths
                    # if the part checksum is the same
                    and archive.index.prev_archive.paths[part_ref.path].variation
                    == part_ref.variation
                )

                if is_modified:
                    archive.index.is_part_modified.add(part_ref.variation)
                    archive.index.is_assembly_modified.add(part_ref.id)

                # add part reference to root assembly and archive
                root_assembly.add_part_ref(part_ref, archive)

                # add part to inventory
                if part_ref.variation.checksum not in archive.inventory.parts:
                    archive.inventory.parts[part_ref.variation.checksum] = base_part

                ArchiveHelper.process_variations(part_ref, cq_subassembly, archive)

        return assemblies, is_modified

    @staticmethod
    def process_variations(
        part_ref: PartRef,
        cq_assembly: cq.Assembly,
        archive: CadArchive,
    ):
        # add part variation to index
        part_checksum = part_ref.variation.checksum

        # derive variation from color
        part_color = (
            list(CadHelper.rgba_float_to_int(cq_assembly.color.toTuple()))
            if cq_assembly.color
            else None
        )
        existing_variation = archive.inventory.get_variation_from_color(
            part_ref.variation.checksum, part_color
        )

        if part_checksum not in archive.inventory.catalog.items:
            archive.inventory.catalog.items[part_checksum] = CatalogItem(
                name=part_ref.name, variations=[]
            )

        # if variation does not exist, create a new one, otherwise add part reference
        if not existing_variation:
            part_variation = InventoryPartVariation(
                id=part_ref.variation.id,
                references=[part_ref.id],
                color=part_color,
            )
            archive.inventory.catalog.items[part_checksum].variations.append(
                part_variation
            )
        else:
            if part_ref.id not in existing_variation.references:
                existing_variation.references.append(part_ref.id)
            part_variation = existing_variation

        # keep the metadata from the previous archive
        if archive.index.prev_archive:
            prev_variation = (
                archive.index.prev_archive.inventory.get_variation_from_color(
                    part_ref.variation.checksum,
                    part_color,
                )
            )
            if prev_variation and not part_variation.metadata:
                part_variation.metadata = prev_variation.metadata

        ArchiveHelper.assign_unique_part_names(part_ref, archive)

    # TODO: Clean this up more
    @staticmethod
    def assign_unique_part_names(part_ref: PartRef, archive: CadArchive):
        part_name = part_ref.name
        index = archive.index
        # check if part name already exists
        if part_name in index.part_names:
            prev_part_ref = index.part_names[part_name]
            if prev_part_ref and part_ref.variation != prev_part_ref.variation:
                # going back and modifying the previous part name
                prev_path_strs = prev_part_ref.path.split("/")
                prev_part_name = "-".join(
                    prev_path_strs[
                        min(archive.config.max_name_depth, len(prev_path_strs)) :
                    ]
                )
                assert (
                    prev_part_name not in index.part_names
                ), f"part name {prev_part_name} already exists"
                archive.inventory.catalog.items[
                    prev_part_ref.variation.checksum
                ].name = prev_part_name

                # modifying the current part name
                path_strs = part_ref.path.split("/")
                part_name = "-".join(
                    path_strs[min(archive.config.max_name_depth, len(path_strs)) :]
                )
                assert (
                    part_name not in index.part_names
                ), f"part name {part_name} already exists"
                archive.inventory.catalog.items[part_ref.variation.checksum].name = (
                    part_name
                )

        else:
            # add part name to index with part_ref it pertains to
            index.part_names[part_name] = part_ref
            archive.inventory.catalog.items[part_ref.variation.checksum].name = (
                part_name
            )

    @staticmethod
    def get_part(
        cq_subassembly: cq.Assembly,
        assembly_path: str,
        abs_location: Optional[Location] = None,
        inventory: Optional[Inventory] = None,
        index: Optional[ArchiveIndex] = None,
        config: Optional[ArchiveConfig] = None,
    ):
        is_part_reference = (config and config.use_part_references) and (
            cq_subassembly.metadata.get("is_part_reference", False)
            # this was old name, just putting for backwards compatibility
            or cq_subassembly.metadata.get("is_reference", False)
        )
        if is_part_reference:
            return ArchiveHelper.get_referenced_part(
                cq_subassembly, assembly_path, inventory
            )
        else:
            normalize_axis = config is not None and config.normalize_axis
            return ArchiveHelper.get_non_reference_part(
                cq_subassembly,
                assembly_path,
                abs_location,
                inventory,
                index,
                normalize_axis,
            )

    @staticmethod
    def get_referenced_part(
        cq_subassembly: cq.Assembly,
        assembly_path: str,
        inventory: Optional[Inventory] = None,
    ):
        base_part = cast(cq.Solid, cast(cq.Workplane, cq_subassembly.obj).val())
        part_checksum = CadHelper.get_shape_checksum(base_part)

        part_color = (
            list(CadHelper.rgba_float_to_int(cq_subassembly.color.toTuple()))
            if cq_subassembly.color
            else None
        )
        variation_id = (
            inventory.find_variation_id(part_checksum, part_color) if inventory else 1
        )
        location = Location.convert(cq_subassembly.loc)
        part_ref = PartRef(
            path=f"{assembly_path}/{cq_subassembly.name}",
            name=cq_subassembly.name,
            variation=InventoryVariationRef(checksum=part_checksum, id=variation_id),
            location=location if not location.is_zero else None,
        )
        return base_part, part_ref

    @staticmethod
    def get_non_reference_part(
        cq_subassembly: cq.Assembly,
        assembly_path: str,
        abs_location: Optional[Location] = None,
        inventory: Optional[Inventory] = None,
        index: Optional[ArchiveIndex] = None,
        normalize_axis: bool = False,
    ):
        if index is None:
            index = ArchiveIndex()

        # TODO: check if this is correct
        part_rel_location = Location.convert(cq_subassembly.loc)
        part_abs_location = part_rel_location.transform(abs_location)
        aligned_part = cast(
            cq.Solid, cast(cq.Workplane, cq_subassembly.obj).val()
        ).located(part_abs_location.to_cq())

        # check if part has been aligned before
        if normalize_axis:
            aligned_checksum = CadHelper.get_shape_checksum(aligned_part)
            if index.prev_archive and aligned_checksum in index.aligned_refs:
                part_ref = index.aligned_refs[aligned_checksum]
                base_part = index.prev_archive.inventory.parts[
                    part_ref.variation.checksum
                ]
                return base_part, part_ref
        else:
            # if not normalizing axis, then no need to check for aligned part, everything is already fast enough
            aligned_checksum = None

        # otherwise align part and normalize
        part_group = (
            np.round(aligned_part.Area(), 3),
            len(cast(Sized, aligned_part._entities("Vertex"))),
        )
        normalized_part, offset, rotmat = CadHelper.normalize_part(
            aligned_part, normalize_axis
        )

        # check if part has been normalized before
        if part_group not in index.base_parts:
            base_part = normalized_part
            index.base_parts[part_group] = normalized_part
        else:
            # align part with previously normalized part (in case of symetric inertial axis)
            base_part = index.base_parts[part_group]
            rot_mat_adjustment = CadHelper.align_parts(base_part, normalized_part)
            rotmat = rotmat.dot(rot_mat_adjustment)

        part_checksum = CadHelper.get_shape_checksum(base_part)
        part_color = (
            list(CadHelper.rgba_float_to_int(cq_subassembly.color.toTuple()))
            if cq_subassembly.color
            else None
        )
        variation_id = (
            inventory.find_variation_id(part_checksum, part_color) if inventory else 1
        )

        part_ref = PartRef(
            path=f"{assembly_path}/{cq_subassembly.name}",
            name=cq_subassembly.name,
            variation=InventoryVariationRef(checksum=part_checksum, id=variation_id),
            location=Location(
                position=offset,
                orientation=rotmat,
            ),
        )

        # assert alignment is correct
        # CadHelper.assert_correctly_aligned(base_part, aligned_part, rotmat, offset)

        # cache aligned part
        if aligned_checksum:
            index.aligned_refs[aligned_checksum] = part_ref

        return base_part, part_ref
