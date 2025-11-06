#!/bin/bash
# Install Archy Executor as a systemd user service

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Navigate to project root (../../ from scripts/install/)
ARCHY_DIR="$(cd "$SCRIPT_DIR/../../" && pwd)"
SERVICE_FILE="$ARCHY_DIR/archy-executor-user.service"
SYSTEMD_DIR="$HOME/.config/systemd/user"

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}[*]${NC} Installing Archy Executor as systemd user service..."

# Verify service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo -e "${RED}[-]${NC} Service file not found at: $SERVICE_FILE"
    exit 1
fi

# Create systemd user directory if it doesn't exist
mkdir -p "$SYSTEMD_DIR"

# Copy service file
cp "$SERVICE_FILE" "$SYSTEMD_DIR/archy-executor.service"
echo -e "${GREEN}[+]${NC} Service file copied to $SYSTEMD_DIR/archy-executor.service"

# Update DISPLAY in the service file to match current environment (only if DISPLAY is set)
if [ -n "$DISPLAY" ]; then
    # Use a temporary file to avoid sed errors
    sed "s|Environment=\"DISPLAY=.*\"|Environment=\"DISPLAY=$DISPLAY\"|g" "$SYSTEMD_DIR/archy-executor.service" > "$SYSTEMD_DIR/archy-executor.service.tmp"
    mv "$SYSTEMD_DIR/archy-executor.service.tmp" "$SYSTEMD_DIR/archy-executor.service"
    echo -e "${GREEN}[+]${NC} Updated DISPLAY=$DISPLAY in service file"
else
    echo -e "${YELLOW}[!]${NC} DISPLAY not set, using default in service file"
fi

# Reload systemd daemon
systemctl --user daemon-reload
echo -e "${GREEN}[+]${NC} Systemd daemon reloaded"

# Enable the service to start on login
systemctl --user enable archy-executor.service
echo -e "${GREEN}[+]${NC} Service enabled for auto-start on login"

# Start the service
systemctl --user start archy-executor.service
sleep 2

# Check if service is running
if systemctl --user is-active --quiet archy-executor.service; then
    echo -e "${GREEN}[+]${NC} Service started successfully!"
    echo -e "${GREEN}[+]${NC} Archy Executor is ready to use"
else
    echo -e "${YELLOW}[!]${NC} Service may not have started properly"
    echo -e "${YELLOW}[!]${NC} Check status with: systemctl --user status archy-executor.service"
fi

