#!/bin/bash
# Script untuk membersihkan semua proses aria2

echo "=== Cleaning up aria2 processes ==="

# Kill all aria2 processes
pkill -9 -f aria2c
pkill -9 -f "aria2.*rpc"

# Kill processes on common ports
for port in 6800 6801 6802 6803 6804 6881 6882 6883; do
    fuser -k ${port}/tcp 2>/dev/null
    fuser -k ${port}/udp 2>/dev/null
done

# Remove session files
rm -f ~/.aria2/aria2.session
rm -f ~/.config/zeta/aria2/aria2.session

echo "Cleanup complete!"
echo "Now start Zeta Manager fresh."
