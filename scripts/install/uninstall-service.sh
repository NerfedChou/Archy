#!/bin/bash
# Uninstall Archy Executor systemd service

SYSTEMD_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SYSTEMD_DIR/archy-executor.service"

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}[!]${NC} Uninstalling Archy Executor systemd service..."

# Stop the service
systemctl --user stop archy-executor.service 2>/dev/null || true
echo -e "${GREEN}[+]${NC} Service stopped"

# Disable the service
systemctl --user disable archy-executor.service 2>/dev/null || true
echo -e "${GREEN}[+]${NC} Service disabled"

# Remove service file
if [[ -f "$SERVICE_FILE" ]]; then
    rm -f "$SERVICE_FILE"
    echo -e "${GREEN}[+]${NC} Service file removed"
fi

# Reload systemd daemon
systemctl --user daemon-reload
echo -e "${GREEN}[+]${NC} Systemd daemon reloaded"

# Kill any remaining daemon processes
pkill -f "archy-executor" 2>/dev/null || true
rm -f /tmp/archy.sock 2>/dev/null || true

echo -e "${GREEN}[+]${NC} Archy service uninstalled successfully"

