#!/bin/bash

# Setup Docker
curl -sSL https://get.docker.com/ | sudo sh
sudo groupadd -f docker
sudo usermod -aG docker $USER
