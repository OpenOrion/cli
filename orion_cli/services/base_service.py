import os
import click

class BaseService:
    def generate(self, step_file, project_path, project_name):
        # Create directory structure
        parts_path = os.path.join(project_path, "parts")
        assemblies_path = os.path.join(project_path, "assemblies", project_name)

        try:
            os.makedirs(parts_path, exist_ok=True)
            os.makedirs(assemblies_path, exist_ok=True)

            # Create README.md and assembly.yml in assemblies/project_name
            readme_path = os.path.join(assemblies_path, "README.md")
            assembly_yml_path = os.path.join(assemblies_path, "assembly.yml")

            with open(readme_path, "w") as readme_file:
                readme_file.write(f"# {project_name} Assembly\n")

            with open(assembly_yml_path, "w") as assembly_yml_file:
                assembly_yml_file.write(
                    "assembly:\n  description: Assembly configuration\n"
                )

            # Create .gitignore in the top-level directory
            gitignore_path = os.path.join(project_path, ".gitignore")

            with open(gitignore_path, "w") as gitignore_file:
                gitignore_file.write(".DS_Store\n")

            click.echo(f"Created directory structure under {project_path}")
        except Exception as e:
            click.echo(f"Error creating directory structure: {e}")
