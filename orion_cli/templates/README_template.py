README_TEMPLATE = lambda NAME, REMOTE_URL, COVER_IMAGE_PATH: f"""
# {NAME}

{f"![{COVER_IMAGE_PATH}]({COVER_IMAGE_PATH})" if COVER_IMAGE_PATH else ""}

## Table of Contents
- [assemblies](./assemblies)
A list of all assemblies in the archive.

- [inventory](./inventory)
    - [parts](./inventory/parts)
    A list of all parts in the archive.

    - [catalog.json](./inventory/catalog.json)
    A JSON catalog containing all part variations in the archive.

- [assets](./assets)
A list of all assets in the archive.

- [config.yaml](./config.yaml)
A configuration file containing archive settings.

{f"## Download" if REMOTE_URL else ""}
{f"`git clone {REMOTE_URL}`" if REMOTE_URL else ""}



<br />
generated with ❤️ by orion-cli
"""

