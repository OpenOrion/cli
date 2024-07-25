
# Orion CLI

Command-line tool for Open Orion PLM.

## Description

Orion CLI is a command-line interface (CLI) tool designed for managing projects within the Open Orion PLM system.

## Features

- Create new projects from step file
- Create revisions changes to step file
- Deploy changes to remote git repository.
- Display project 

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

In the "robot" directory, you will find the `README.md` file with project information, the `Robot.step` file (which is the duplicate of the step file), the `assemblies` folder (containing deconstructed assemblies and subassemblies), the `config.yaml` file (with project specific configurations), and the `inventory` folder (containing all individual parts). Once the project creation is complete Orion CLI will initialize a new git repository in the project folder and create an initial commit.

#### Inventory

The inventory folder will include breps of all parts in the assembly and a `catalog.json` file containing part and assembly metadata.

Here is an example structure of the inventory folder:

```
inventory
├── catalog.json
└── parts
    ├── 2995K11_Swivel_Joint_<2>_0-Part_1_0.brep
    ├── 51T_HDT5_15MM_Belt_Knee_Left_0.brep
    ├── 6mm_Bearing_5.brep
    ├── 92981A105_Alloy_Steel_Shoulder_Screws_3.brep
    ├── Ankle_0.brep
    ├── Arducam_Case_0.brep
    ├── Base_0.brep
    ├── Belt_Thigh_Left_0.brep
    ├── Bottom_Torso_Lower_Half_0.brep
    ├── Camera_Mount_0.brep
    ├── Elbow_0.brep
    ├── Foot_0.brep
    ├── Gripper_1.brep
    ├── Head_0.brep
    ├── Hips_0.brep
    ├── LCD_1.brep
    ├── Neck_0.brep
    ├── Right_Leg_<1>_0-X10_<1>_0-Inner_0.brep
    ├── Shoulder_Inner_0.brep
    ├── Spur_gear__26_teeth__0.brep
    ├── Thigh_HTD_5mm_44T_Pulley_0.brep
    ├── Top_Torso_0.brep
    ├── Wrist_0.brep
    ├── X4_<1>_0-Inner_0.brep
    ├── X6_<2>_0-Inner_0.brep
    └── XPT2046_Touch_0.brep

```

### Assemblies

The `assemblies` folder contains a nested directory structure that represents all the subassemblies in the project step file. Each subassembly is organized in its own directory within the `assemblies` folder.

Here is an example structure of the `assemblies` folder:

```
assemblies
└── Robot
    ├── Head_<1>_0
    │   ├── X4_<1>_0
    │   ├── X4_<2>_0
    │   └── assembly.json
    ├── Left_Arm_<2>_0
    │   ├── Hand_<1>_0
    │   │   ├── X4_<1>_0
    │   │   ├── X4_<2>_0
    │   │   └── assembly.json
    │   ├── X4_<1>_0
    │   ├── X6_<1>_0
    │   ├── X6_<2>_0
    │   ├── X8_<1>_0
    │   └── assembly.json
    └── assembly.json

```

This nested directory structure helps organize and manage the subassemblies within the project, making it easier to navigate and work with the individual components.

### Create a Revision for a Project

If you have made changes to your step file or modified the step file in the project directory, you may want your project directory to reflect these changes. The `orion revision` command allows you to create a revision for your project.

To create a revision from inside the project directory using the project step file, run the following command from inside your project directory:

```bash
orion revision
```

If you want to create revision from step file outside the current project directory `/a/path/to/cad/robot.step`, you can run the following command:

```bash
orion revision --cad_path /a/path/to/cad/robot.step
```

After running the command, your project should be updated and you will be asked if you would like to stage the changes.

### Deploy the project

To deploy a revisioned project, you can use the `orion deploy` command. Before using this command, make sure you have set a remote URL for your project either during the creation process or manually in the `config.yaml` file under the `repo_url` field. Additionally, ensure that you have git properly configured on your system and are inside the project directory.

To deploy the project, navigate to the project directory and run the following command:

```bash
orion deploy
```

You will be prompted to enter a deployment message. Once you provide the message, the command will push the project to the remote repository.

Please note that this command assumes you have already created a revision for your project using the `orion revision` command.

### Display the project

To view the reconstructed CAD project, you can use the `orion display` command. This command should be run from inside the project directory.

When you run the `orion display` command, it will generate an `index.html` file in the `.orion_cache` folder of the project. You can open this file in a web browser to view the project reconstructed into CAD.

Please note that the `orion display` command requires the project to have already been created.
