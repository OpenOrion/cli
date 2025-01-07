# MIT License
#
# Copyright (c) 2025 Open Orion, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from typing import Optional
from pydantic import BaseModel, Field
from pathlib import Path
import yaml


# Assuming ProjectOptions is defined in cad_service.py
from orion_cli.services.cad_service import ProjectOptions

CadPath = str
GitRepoUrl = str


class ProjectConfig(BaseModel):
    name: str
    options: ProjectOptions = Field(default_factory=ProjectOptions)
    repo_url: Optional[GitRepoUrl] = None
    cad_path: Optional[CadPath] = None

class ConfigHelper:
    @staticmethod
    def load_config(config_path: Path) -> ProjectConfig:
        with open(config_path, 'r') as file:
            config_data = yaml.safe_load(file)
        return ProjectConfig(**config_data)
    
    @staticmethod
    def save_config(config_path: Path, config: ProjectConfig):
        with open(config_path, 'w') as file:
            yaml.dump(config.dict(), file)

# class GlobalConfig(BaseModel):
#     default_project_options: ProjectOptions = Field(default_factory=ProjectOptions)

# class UserConfig(BaseModel):
#     project_base_dirs: List[Path] = Field(default_factory=list)
#     current_project: Optional[str] = None
#     global_config: GlobalConfig = Field(default_factory=GlobalConfig)

# class OrionConfig:
#     def __init__(self):
#         self.user_config = self._load_user_config()
#         self.project_config = self._load_project_config()

#     def _load_user_config(self) -> UserConfig:
#         user_config_path = Path.home() / ".orion" / "config.yaml"
#         if user_config_path.exists():
#             with open(user_config_path, "r") as f:
#                 return UserConfig.model_validate(yaml.safe_load(f))
#         return UserConfig()

#     def _load_project_config(self) -> ProjectConfig:
#         project_path = self.get_project_path()
#         if project_path:
#             config_path = project_path / "orion.yaml"
#             if config_path.exists():
#                 with open(config_path, "r") as f:
#                     return ProjectConfig.model_validate(yaml.safe_load(f))
#         return ProjectConfig(name=self.user_config.current_project or "")

#     def save(self):
#         # Save user config
#         user_config_path = Path.home() / ".orion" / "config.yaml"
#         user_config_path.parent.mkdir(parents=True, exist_ok=True)
#         with open(user_config_path, "w") as f:
#             yaml.dump(self.user_config.model_dump(), f)

#         # Save project config
#         project_path = self.get_project_path()
#         if project_path:
#             config_path = project_path / "orion.yaml"
#             with open(config_path, "w") as f:
#                 yaml.dump(self.project_config.model_dump(), f)

#     def get_project_path(self) -> Optional[Path]:
#         if not self.user_config.current_project:
#             return None
#         for base_dir in self.user_config.project_base_dirs:
#             project_dir = base_dir / self.user_config.current_project
#             if project_dir.exists():
#                 return project_dir
#         return None

#     def set_current_project(self, name: str, path: Path):
#         self.user_config.current_project = name
#         if path.parent not in self.user_config.project_base_dirs:
#             self.user_config.project_base_dirs.append(path.parent)
#         self.project_config = ProjectConfig(name=name)

#     def get_project_config(self) -> ProjectConfig:
#         return self.project_config

#     def update_project_config(self, **kwargs):
#         self.project_config = self.project_config.model_copy(update=kwargs)

#     def get_global_config(self) -> GlobalConfig:
#         return self.user_config.global_config

#     def update_global_config(self, **kwargs):
#         self.user_config.global_config = self.user_config.global_config.model_copy(update=kwargs)