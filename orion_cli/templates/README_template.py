README_TEMPLATE = lambda NAME, REMOTE_URL: f"""
# {NAME}

## Table of Contents
- [assemblies](/assemblies)
- [assets](/assets)
- [inventory](/inventory)
- [config.yaml](/config.yaml)

{f"## Download" if REMOTE_URL else ""}
{f"`git clone {REMOTE_URL}`" if REMOTE_URL else ""}
"""

