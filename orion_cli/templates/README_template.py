README_TEMPLATE = lambda NAME, REMOTE_URL, COVER_IMAGE_PATH: f"""
# {NAME}

{f"![{COVER_IMAGE_PATH}]({COVER_IMAGE_PATH})" if COVER_IMAGE_PATH else ""}

## Table of Contents
- [assemblies](./assemblies)
A list of all assemblies in the project.

- [inventory](./inventory)
    - [parts](./inventory/parts)
    A list of all parts in the project.

    - [catalog.json](./inventory/catalog.json)
    A JSON catalog containing all part variations in the project.

- [assets](./assets)
A list of all assets in the project.

- [config.yaml](./config.yaml)
A configuration file containing project settings.

{f"## Download" if REMOTE_URL else ""}
{f"`git clone {REMOTE_URL}`" if REMOTE_URL else ""}



<br />
generated with ❤️ by orion-cli
"""

