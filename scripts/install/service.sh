#!/bin/bash
# Install Archy Executor as a systemd user service

set -e

ARCHY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Navigate to project root from scripts/install/
ARCHY_DIR="$(cd "$ARCHY_DIR/../../.." && pwd)"
SERVICE_FILE="$ARCHY_DIR/archy-executor.service"
SYSTEMD_DIR="$HOME/.config/systemd/user"

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}[*]${NC} Installing Archy Executor as systemd user service..."

# Create systemd user directory if it doesn't exist
mkdir -p "$SYSTEMD_DIR"

# Copy service file
cp "$SERVICE_FILE" "$SYSTEMD_DIR/archy-executor.service"
echo -e "${GREEN}[+]${NC} Service file copied to $SYSTEMD_DIR/archy-executor.service"

# Reload systemd daemon
systemctl --user daemon-reload
echo -e "${GREEN}[+]${NC} Systemd daemon reloaded"

# Enable the service to start on login
systemctl --user enable archy-executor.service
echo -e "${GREEN}[+]${NC} Service enabled for auto-start on login"

# Start the service
systemctl --user start archy-executor.service
sleep 2

# Check if it's running
if systemctl --user is-active --quiet archy-executor.service; then
    echo -e "${GREEN}[+]${NC} Service started successfully!"
    echo ""
    echo -e "${GREEN}✓ Archy is now installed as a systemd service!${NC}"
    echo ""
    echo "Useful commands:"
    echo "  systemctl --user status archy-executor.service    # Check service status"
    echo "  systemctl --user start archy-executor.service     # Start manually"
    echo "  systemctl --user stop archy-executor.service      # Stop manually"
    echo "  systemctl --user restart archy-executor.service   # Restart"
    echo "  systemctl --user disable archy-executor.service   # Disable auto-start"
    echo "  journalctl --user -u archy-executor.service -f    # View live logs"
    echo ""
else
    echo -e "${RED}[-]${NC} Service failed to start!"
    echo "Check logs with: journalctl --user -u archy-executor.service -n 50"
    exit 1
fi

