FROM mcr.microsoft.com/devcontainers/miniconda:0-3

RUN apt-get update -y && \
  apt install -y libgl1-mesa-glx curl && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*


# Install Python dependencies from requirements.txt if it exists
USER vscode
RUN conda install -c conda-forge -c cadquery cadquery=master -y
