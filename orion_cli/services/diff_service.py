from typing import Literal, Optional, Union
from typing import Optional

import numpy as np
from typing import Optional, Dict

from orion_cli.models.archive import Assembly, CadArchive

ItemId = str

DeleteType = Literal["delete"]


class LocationModification:
    position: Optional[tuple[float, float, float]] = None
    rotation: Optional[tuple[float, float, float]] = None


class AssemblyModification:
    path: str
    location: Optional[LocationModification] = None


class PartModification:
    path: str
    location: Optional[LocationModification] = None


class VariableModification:
    path: str
    value: Optional[str] = None


class CodeModification:
    path: str
    code: Optional[str] = None


class DiffPatch:
    assembly: Dict[ItemId, Union[AssemblyModification, DeleteType]] = {}
    part: Dict[ItemId, Union[PartModification, DeleteType]] = {}
    variable: Dict[ItemId, Union[VariableModification, DeleteType]] = {}
    code: Dict[ItemId, Union[DeleteType, CodeModification]] = {}


class DiffService:
    @staticmethod
    def apply_assembly_diff(
        project: CadArchive,
        diff: Union[AssemblyModification, PartModification],
        assembly_id: Assembly,
    ):
        is_assembly = isinstance(diff, AssemblyModification)
        child = (
            project.assemblies[assembly_id]
            if is_assembly
            else project.parts[assembly_id]
        )

        new_parent_path = "/".join(diff.path.split("/")[:-1]) or "/"
        new_child_name = diff.path.split("/")[-1]
        new_parent_assembly = project.get_assembly_by_path(new_parent_path)

        if diff.delete:
            if is_assembly:
                new_parent_assembly.remove_child(assembly_id, project)
            else:
                new_parent_assembly.remove_part_ref(assembly_id, project)
            return

        if diff.location:
            if diff.location.position:
                child.location.position = np.array(diff.location.position)
            if diff.location.rotation:
                child.location.rotation = np.array(diff.location.rotation)

        if diff.path:
            # remove assembly from previous parent
            parent_assembly = project.get_assembly_by_path(child.parent_path)

            # remove from old parent and add to new parent
            if is_assembly:
                parent_assembly.remove_child(assembly_id, project)
                new_parent_assembly.add_child(child, project, new_child_name)
            else:
                parent_assembly.remove_part_ref(assembly_id, project)
                new_parent_assembly.add_part_ref(child, project, new_child_name)

    @staticmethod
    def apply_patch(project: CadArchive, patch: DiffPatch):
        new_project = project.model_copy(deep=True)
        for assembly_id, diff in patch.assembly.items():
            DiffService.apply_assembly_diff(new_project, diff, assembly_id)
        for part_id, diff in patch.part.items():
            DiffService.apply_assembly_diff(new_project, diff, part_id)
        return new_project
