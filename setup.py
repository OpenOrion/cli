from setuptools import setup, find_packages

# Function to read the requirements.txt file
def parse_requirements(filename):
    with open(filename, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

# Read the requirements from requirements.txt
requirements = parse_requirements('requirements.txt')
dev_requirements = parse_requirements('requirements_dev.txt')

setup(
    name="orion-cli",
    version="0.1.3",
    description="Command-line tool for Open Orion PLM",
    author="Afshawn Lotfi",
    author_email="afshawn@openorion.org",
    license="Apache-2.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,  # This reads from requirements.txt
    extras_require={
        "cq": [
            "cadquery==2.4.0; platform_machine != 'arm64'",
            "cadquery; sys_platform == 'darwin' and platform_machine == 'arm64'",
            "ocp-tessellate-orion==0.0.1"
        ],
        "dev": dev_requirements,
    },
    entry_points={
        'console_scripts': [
            'orion = orion_cli.cli:cli',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10,<3.12",
)
