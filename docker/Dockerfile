FROM ubuntu:22.04

# Set working directory
SHELL [ "bash", "-c" ]
ENV DEBIAN_FRONTEND=noninteractive
# ENV NVIDIA_VISIBLE_DEVICES all
# ENV NVIDIA_DRIVER_CAPABILITIES alls

WORKDIR /workspace

# Update and install essential tools
RUN apt update && \
    apt install -yq \
        ffmpeg \
        dkms \
        build-essential \
        jq \
        tree \
        tldr \
        wget \
        curl \
        git \
        sudo \
        locales \
        net-tools \
        netcat \
        software-properties-common \
        rsync \
        autoconf \
        automake \
        libtool \
        pkg-config \
        ca-certificates


# Configure locale settings
RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

# Install core X11 components (lighter than a full desktop environment)
RUN apt update && \
    apt install -y \
    xserver-xorg \
    xauth \
    x11-apps \
    mesa-utils \
    xdg-utils \
    xterm \
    xvfb \
    xdotool \
    scrot \
    imagemagick \
    apt-transport-https \
    dbus-x11

# Create the dbus socket directory
RUN mkdir -p /run/dbus && chown messagebus:messagebus /run/dbus


# Install fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-wqy-microhei && \
    apt-get clean


# Install lightweight desktop environment Xfce4
RUN apt install -y \
    xubuntu-desktop
#     xfce4 \
#     xfce4-terminal \
#     thunar \
#     xfce4-panel \
#     xfce4-settings \
#     xfce4-session \
#     xfwm4 \
#     xfdesktop4 \
#     lightdm \
#     xfce4-goodies \
#     elementary-xfce-icon-theme

# Install NVIDIA drivers and libraries (wildcard to suit various systems)
# RUN apt update && \
#     apt install -y \
#     nvidia-driver-530 \
#     libnvidia-gl-530 \
#     nvidia-cuda-toolkit 
    

# Add the Mozilla Team PPA for Firefox ESR
RUN add-apt-repository ppa:mozillateam/ppa -y && \
    apt-get update -y

ENV MOZ_DISABLE_CONTENT_SANDBOX=1
ENV MOZ_DISABLE_GMP_SANDBOX=1
ENV MOZ_DISABLE_NPAPI_SANDBOX=1
ENV MOZ_DISABLE_GPU_SANDBOX=1


# Install dependencies
RUN apt update && apt install -y \
    libglu1-mesa \
    libxv1 \
    libxtst6 \
    libxrender1 \
    libssl-dev  \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev \
    libkrb5-dev \
    # USER apps
    # libreoffice \
    firefox-esr \
    xpdf \
    gedit \
    xpaint \
    unzip \
    galculator

# Add symlink for firefox-esr to firefox
RUN ln -s /usr/bin/firefox-esr /usr/bin/firefox

# Set Firefox as system default browser
RUN update-alternatives --set x-www-browser /usr/bin/firefox-esr && \
    update-alternatives --set gnome-www-browser /usr/bin/firefox-esr || true

ENV BROWSER=/usr/bin/firefox-esr


# Install Chrome
RUN wget -q -O google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get update && \
    apt-get install -y ./google-chrome.deb && \
    rm google-chrome.deb && \
    apt-get -f install -y

# Add symlink for ease
# RUN ln -s /usr/bin/google-chrome-stable /usr/bin/google-chrome || true
# Add the --no-sandbox and other flags to remove welcome window
RUN echo '#!/bin/bash' | tee /usr/local/bin/google-chrome >/dev/null && \
    echo "/usr/bin/google-chrome-stable --no-sandbox --disable-dev-shm-usage --no-first-run --disable-fre --disable-gpu --disable-software-rasterizer --disable-background-networking --disable-dbus \"\$@\"" | tee -a /usr/local/bin/google-chrome >/dev/null  && \
    chmod +x /usr/local/bin/google-chrome

# Install noVNC (for web-based access)
RUN git clone --branch v1.5.0 https://github.com/novnc/noVNC.git /opt/noVNC && \
    git clone --branch v0.12.0 https://github.com/novnc/websockify /opt/noVNC/utils/websockify && \
    ln -s /opt/noVNC/vnc.html /opt/noVNC/index.html
# RUN wget https://github.com/VirtualGL/virtualgl/releases/download/3.1.2/virtualgl_3.1.2_amd64.deb
# RUN dpkg -i virtualgl_3.1.2_amd64.deb
# RUN rm virtualgl_3.1.2_amd64.deb

RUN wget -4 https://github.com/TurboVNC/turbovnc/releases/download/3.1.4/turbovnc_3.1.4_amd64.deb
RUN dpkg -i turbovnc_3.1.4_amd64.deb
# RUN rm turbovnc_3.1.4_amd64.deb

# Install Ollama (for local LLM serving)
# RUN curl -fsSL https://ollama.com/install.sh | bash

# Create a new user and configure permissions
RUN groupadd vglusers
RUN useradd -m agent
RUN usermod -aG sudo,video,vglusers agent
RUN echo 'agent:123' | chpasswd

USER agent
ENV HOME=/home/agent

# Set up VirtualGL (for OpenGL rendering in virtual environments)
# RUN mkdir -p /etc/opt/VirtualGL && \
#     echo "export VGL_DISPLAY=:0" > /etc/opt/VirtualGL/vgl_xauth_key && \
#     chmod 644 /etc/opt/VirtualGL/vgl_xauth_key 
    # /opt/VirtualGL/bin/vglserver_config -config +s +f -t

# Configure TurboVNC settings
# RUN echo "useVGL=true" >> /etc/turbovncserver.conf
USER agent
ENV USER=agent
SHELL [ "bash", "-c" ]

# Installing Additional langauge/packages
ENV NODE_VERSION=22

# Install NVM
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash

# Ensure that nvm is sourced in the shell environment and install Node.js
RUN echo 'export NVM_DIR="$HOME/.nvm"' >> ~/.bashrc && \
    echo '[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"' >> ~/.bashrc && \
    echo 'export PATH="$NVM_DIR/versions/node/v$NODE_VERSION/bin:$PATH"' >> ~/.bashrc

# Install Node.js
RUN . "$HOME/.nvm/nvm.sh" && nvm install ${NODE_VERSION}
# Verify and add packages
RUN . "$HOME/.nvm/nvm.sh" && node --version && npm --version && npm install -g yarn node-gyp


# Install and configure Miniconda
RUN mkdir -p ~/miniconda3 && \
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh && \
    bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3 && \
    rm ~/miniconda3/miniconda.sh && \
    ~/miniconda3/bin/conda init --all

# Set environment variables for display and TurboVNC
RUN echo 'export DISPLAY=:4' >> ~/.bashrc && \
    echo 'export XDG_SESSION_TYPE=x11' >> ~/.bashrc && \
    echo 'export PATH=/opt/TurboVNC/bin:$PATH' >> ~/.bashrc && \
    echo 'alias google-chrome="google-chrome --no-sandbox --disable-dev-shm-usage --no-first-run --disable-fre"' >>~/.bashrc
    # echo 'export WIDTH=1024' >> ~/.bashrc && \
    # echo 'export HEIGHT=768' >> ~/.bashrc
#     echo 'export DISPLAY=:1' >> ~/.bashrc && \
#     echo 'export VGL_DISPLAY=:0' >> ~/.bashrc && \
#     echo 'alias vglrun="/opt/VirtualGL/bin/vglrun"' >> ~/.bashrc
    # echo 'export http_proxy=http://10.29.46.139:7890' >> ~/.bashrc && \
    # echo 'export https_proxy=http://10.29.46.139:7890' >> ~/.bashrc && \


# Set startup command for the VNC server
USER agent

# Set Firefox as default browser for user session
RUN mkdir -p /home/agent/.config /home/agent/.local/share/applications && \
    echo "[Default Applications]\n\
text/html=firefox-esr.desktop\n\
x-scheme-handler/http=firefox-esr.desktop\n\
x-scheme-handler/https=firefox-esr.desktop\n\
x-scheme-handler/about=firefox-esr.desktop\n\
x-scheme-handler/unknown=firefox-esr.desktop\n\
application/xhtml+xml=firefox-esr.desktop\n\
application/xml=firefox-esr.desktop" > /home/agent/.config/mimeapps.list

# Also set for Xfce specifically
RUN mkdir -p /home/agent/.config/xfce4 && \
    echo "WebBrowser=firefox-esr" > /home/agent/.config/xfce4/helpers.rc


RUN mkdir /home/agent/.vnc/
RUN echo -e '#!/bin/sh\n \
# Start D-Bus\n\
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then\n\
    eval $(dbus-launch --sh-syntax)\n\
fi\n\
xrdb "$HOME/.Xresources"\n \
xsetroot -solid grey\n \
export XKL_XMODMAP_DISABLE=1\n \
/etc/X11/Xsession\n \
unset SESSION_MANAGER\n \
unset DBUS_SESSION_BUS_ADDRESS\n \
x-session-manager & xfdesktop & xfce4-panel & xfce4-menu-plugin & xfsettingsd & xfconfd & xfwm4' > /home/agent/.vnc/xstartup && \
chmod +x /home/agent/.vnc/xstartup
