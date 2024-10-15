
# Orion CLI

Command-line tool for Open Orion PLM.

## Description

Orion CLI is a command-line interface (CLI) tool designed for managing archives within the Open Orion PDM system.

### Demo Video
[![Youtube Demo](https://img.youtube.com/vi/QfzNhCsARKY/0.jpg)](https://www.youtube.com/watch?v=QfzNhCsARKY)

## Features

- Create new archives from step file
- Create revisions changes to step file
- Deploy changes to remote git repository.
- Display archive

## Requirements

- Python 3.9 or higher
- pip
- git (configured with remote credentials if using deploy)

## Installation

To install Orion CLI, you can use pip. Open your terminal and run the following command:

```bash
# Install without Cadquery
pip install orion-cli

# Install with Cadquery
pip install orion-cli[cq]
```

If you'd like to install your own version of CQ checkout their [Github](https://github.com/CadQuery/cadquery) 

Make sure you have Python 3.9 or higher installed before running the command. 

# Dev Setup

```bash
git clone https://github.com/OpenOrion/meshql.git
cd cli

# Bash shell
pip install .[cq,dev]

# Zsh shell
pip install .\[cq,dev\]
```

## Usage

> ⚠️ **Note:** The first time you use Orion CLI, it may be slow as it configures some dependencies. Please be patient during this initial setup process.

After installing via pip you can commands as follows:

### Create a New Archive

To create a new archive, run:

```bash
orion create

# to include svg and markdown assets
orion create --include-assets
```

To create a new archive, you will be prompted for the following information:

- archive name
- Path to the step file being used for the archive

Additionally, you will be asked if you want to provide a GitHub remote URL. If you choose to do so, you will be prompted to provide the URL.

After providing the necessary information, the `orion create` command will create a directory with the same name as the archive name that you provided.

In the created directory, Orion CLI will copy over the provided step file, create an assemblies folder with deconstructed assemblies and subassemblies, create an inventory folder with all individual parts, a .gitignore file, a README.md file, and a config.yaml file with archive specific configurations.

### Example

For example, if you create a archive called "robot" and provide a step file with the path `/a/path/to/Robot.step`, the `orion create` command will produce a directory named "robot" with the following structure:

```
robot
├── README.md
├── Robot.step
├── assemblies
├── config.yaml
└── inventory
```

In the "robot" directory, you will find the `README.md` file with archive information, the `Robot.step` file (which is the duplicate of the step file), the `assemblies` folder (containing deconstructed assemblies and subassemblies), the `config.yaml` file (with archive specific configurations), and the `inventory` folder (containing all individual parts). Once the archive creation is complete Orion CLI will initialize a new git repository in the archive folder and create an initial commit.

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

The `assemblies` folder contains a nested directory structure that represents all the subassemblies in the archive step file. Each subassembly is organized in its own directory within the `assemblies` folder.

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

This nested directory structure helps organize and manage the subassemblies within the archive, making it easier to navigate and work with the individual components.

### Create a Revision for a archive

If you have made changes to your step file or modified the step file in the archive directory, you may want your archive directory to reflect these changes. The `orion revision` command allows you to create a revision for your archive.

To create a revision from inside the archive directory using the archive step file, run the following command from inside your archive directory:

```bash
orion revision
```

If you want to create revision from step file outside the current archive directory `/a/path/to/cad/robot.step`, you can run the following command:

```bash
orion revision --cad_path /a/path/to/cad/robot.step
```

After running the command, your archive should be updated and you will be asked if you would like to stage the changes.

### Deploy the archive

To deploy a revisioned archive, you can use the `orion deploy` command. Before using this command, make sure you have set a remote URL for your archive either during the creation process or manually in the `config.yaml` file under the `repo_url` field. Additionally, ensure that you have git properly configured on your system and are inside the archive directory.

To deploy the archive, navigate to the archive directory and run the following command:

```bash
orion deploy
```

You will be prompted to enter a deployment message. Once you provide the message, the command will push the archive to the remote repository.

Please note that this command assumes you have already created a revision for your archive using the `orion revision` command.

### Display the archive

To view the reconstructed archive, you can use the `orion display` command. This command should be run from inside the archive directory:

```bash
orion display
```

When you run the `orion display` command, it will generate an `index.html` file in the `.orion_cache` folder of the archive. You can open this file in a web browser to view the archive reconstructed into CAD.

Please note that the `orion display` command requires the archive to have already been created.
