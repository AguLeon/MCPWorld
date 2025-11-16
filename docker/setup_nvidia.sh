#!/bin/bash

echo "NVIDIA Container Toolkit installation starting..."

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg &&
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' |
        sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt update

sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

docker run --rm --gpus all ubuntu nvidia-smi

echo "NVIDIA Container Toolkit installation complete."
