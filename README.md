
# Orion CLI

Command-line tool for Open Orion PLM.

## Description

Orion CLI is a command-line interface (CLI) tool designed for managing projects within the Open Orion PLM system.

## Features

- Create new projects from step file
- Create revisions changes to step file
- Deploy changes to remote git repository.

## Requirements

- Python 3.9 or higher
- pip
- git (configured with remote credentials if using deploy)


## Installation

To install Orion CLI, you can use pip. Open your terminal and run the following command:

```bash
pip install orion-cli
```

Make sure you have Python 3.9 or higher installed before running the command. 


## Usage

After installing the dependencies, you can run the CLI commands using Poetry. Here are some examples:

### Create a New Project

To create a new project, run:

```bash
orion create
```

To create a new project, you will be prompted for the following information:

- Project name
- Path to the step file being used for the project

Additionally, you will be asked if you want to provide a GitHub remote URL. If you choose to do so, you will be prompted to provide the URL.

After providing the necessary information, the `orion create` command will create a directory with the same name as the project name that you provided.

In the created directory, Orion CLI will copy over the provided step file, create an assemblies folder with deconstructed assemblies and subassemblies, create an inventory folder with all individual parts, a .gitignore file, a README.md file, and a config.yaml file with project specific configurations.

### Example

For example, if you create a project called "robot" and provide a step file with the path `/a/path/to/Robot.step`, the `orion create` command will produce a directory named "robot" with the following structure:

```
robot
├── README.md
├── Robot.step
├── assemblies
├── config.yaml
└── inventory
```

In the "robot" directory, you will find the `README.md` file, the `Robot.step` file (which is the provided step file), the `assemblies` folder (containing deconstructed assemblies and subassemblies), the `config.yaml` file (with project specific configurations), and the `inventory` folder (containing all individual parts).

This structure allows you to easily manage and organize your project files within the Orion CLI.

#### Inventory


### Create a Revision for a Project

To create a new revision for a project, run:

```bash
orion revision
```

Expected output:

```
Your project has been revisioned
```

### Deploy the project

To deploy a revisioned, project run:

```bash
orion deploy
```

Expected output:

```
Your project has been deployed
```

## License

[Coming soon]
