#!/bin/bash
# Fmanager Installation Script

# Configuration
APP_NAME="zeta"
INSTALL_DIR="/usr/share/$APP_NAME"
BIN_DIR="/usr/local/bin"

# Check root
if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root"
    exit 1
fi

# Create directories
echo "Installing Zeta Manager to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
chmod 755 "$INSTALL_DIR"

# Copy files
cp -r ./* "$INSTALL_DIR/"
chmod 644 "$INSTALL_DIR"/*.py
chmod 644 "$INSTALL_DIR"/*.settings

# Install default config for root
mkdir -p /root/.config/zeta
cp "$INSTALL_DIR/config.json" /root/.config/zeta/
chmod 644 /root/.config/zeta/config.json

# Install wrapper
echo "Creating executable..."
cp zeta "$BIN_DIR/"
chmod 755 "$BIN_DIR/zeta"

# Create desktop entry
echo "Adding desktop integration..."
cat > /usr/share/applications/zeta.desktop <<EOL
[Desktop Entry]
Name=Zeta Manager
Comment=Terminal File Manager
Exec=zeta
Icon=$INSTALL_DIR/icon.png
Terminal=true
Type=Application
Categories=System;FileTools;
Keywords=file;manager;terminal;
EOL

echo "Installation complete. Run with 'zeta'"
