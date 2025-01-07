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

