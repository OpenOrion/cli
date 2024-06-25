
# Orion CLI

Command-line tool for Open Orion PLM.

## Description

Orion CLI is a command-line interface (CLI) tool designed for managing projects within the Open Orion PLM system. 

## Features

- Create new projects
- Create revisions for projects
- Sync directories

## Requirements

- Python 3.8 or higher
- Poetry

## Installation

### 1. Clone the Repository

First, clone the repository to your local machine:

```bash
git clone git@github.com:username/orion-cli.git
cd orion-cli
```

### 2. Install Poetry

If you do not have Poetry installed, you can install it using the following command:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Add Poetry to your PATH:

For bash:
```bash
echo 'export PATH="$HOME/.poetry/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

For zsh:
```bash
echo 'export PATH="$HOME/.poetry/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### 3. Install Dependencies

Navigate to the project directory and install the dependencies using Poetry:

```bash
poetry install
```

## Usage

After installing the dependencies, you can run the CLI commands using Poetry. Here are some examples:

### Create a New Project

To create a new project, run:

```bash
poetry run orion create
```

Expected output:

```
Your project has been created
```

### Create a Revision for a Project

To create a new revision for a project, run:

```bash
poetry run orion revision
```

Expected output:

```
Your project has been revisioned
```

### Sync Directories

To sync two directories, run:

```bash
poetry run orion sync
```

Expected output:

```
Your project has been synced
```

## Running Tests

To run the tests for this project, use the following command:

```bash
poetry run pytest
```

## License

[Coming soon]
