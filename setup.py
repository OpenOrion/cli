from setuptools import setup, find_packages

setup(
    name="orion-cli",
    version="0.1.1",
    description="Command-line tool for Open Orion PLM",
    author="Christian",
    author_email="christian@openorion.org",
    license="Apache-2.0",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    packages=find_packages(),
    python_requires='>=3.10,<3.12',
    install_requires=[
        "click",
        "requests",
        "pygithub",
        "numpy<2.0.0",
        "pydantic",
        "ocp-tessellate",
        "scipy",
        "cadquery-ocp; platform_machine == 'x86_64'",
        "cadquery; platform_machine == 'x86_64'"
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-click",
            "ipykernel"
        ]
    },
    dependency_links=[
        "https://github.com/OpenOrion/ocp-build-system/releases/download/0.1.0i/cadquery_ocp-7.7.2.1-cp39-cp39-macosx_11_0_arm64.whl; sys_platform == 'darwin' and platform_machine == 'arm64' and python_version == '3.9'",
        "https://github.com/OpenOrion/ocp-build-system/releases/download/0.1.0i/cadquery_ocp-7.7.2.1-cp310-cp310-macosx_11_0_arm64.whl; sys_platform == 'darwin' and platform_machine == 'arm64' and python_version == '3.10'",
        "https://github.com/OpenOrion/ocp-build-system/releases/download/0.1.0i/cadquery_ocp-7.7.2.1-cp311-cp311-macosx_11_0_arm64.whl; sys_platform == 'darwin' and platform_machine == 'arm64' and python_version == '3.11'",
        "https://github.com/OpenOrion/cadquery/releases/download/v1.0.0d/cadquery-1.0.0-py3-none-any.whl; sys_platform == 'darwin' and platform_machine == 'arm64'"
    ],
    entry_points={
        'console_scripts': [
            'orion = orion_cli.cli:cli',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ]
)

