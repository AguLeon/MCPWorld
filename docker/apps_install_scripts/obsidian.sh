#!/bin/bash

# Install needed packages
sudo apt update
sudo apt install -y fuse libfuse2

# Download the obsidian AppImage
wget https://github.com/obsidianmd/obsidian-releases/releases/download/v1.7.7/Obsidian-1.7.7.AppImage -O ~/Obsidian.AppImage

chmod +x ~/Obsidian.AppImage

# Manually extract obsidian
cd ~

~/Obsidian.AppImage --appimage-extract

# Create wrapper script with --no-sandbox flag
# Add symbolic link (So that it becomes visible for the agent)
echo '#!/bin/bash' | sudo tee /usr/local/bin/obsidian >/dev/null
echo "~/squashfs-root/obsidian --no-sandbox \"\$@\"" | sudo tee -a /usr/local/bin/obsidian >/dev/null
sudo chmod +x /usr/local/bin/obsidian

# Create an alias with no-sandbox for easy access
echo 'alias obsidian="~/squashfs-root/obsidian --no-sandbox"' >>~/.bashrc
source ~/.bashrc

# Setup pre-defined global obsidian config files so that it works with the pre-defined vaults
cp -r /workspace/PC-Canary/tests/context_data/obsidian/obsidian/ ~/.config/

cd /workspace
