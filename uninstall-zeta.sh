#!/bin/bash
# Zeta Manager Uninstaller

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root"
    exit 1
fi

echo "Removing Fmanager..."
rm -rf /usr/share/zeta
rm -f /usr/local/bin/zeta
rm -f /usr/share/applications/zeta.desktop

echo "Zeta Manager has been completely removed"
