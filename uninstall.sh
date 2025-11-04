#!/bin/bash

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${RED}  Archy Uninstallation Script${NC}"
echo -e "${BLUE}========================================${NC}"

# Confirmation
echo -e "\n${YELLOW}[!] This will remove all Archy services and data${NC}" 
echo -e "${YELLOW}[!] Continue? (yes/no)${NC}"
read -p ">>> " confirm

if [[ "$confirm" != "yes" ]]; then
    echo -e "${YELLOW}[*] Uninstallation cancelled${NC}"
    exit 0
fi

# Stop and disable MCP systemd service
echo -e "\n${BLUE}[*] Stopping MCP service...${NC}"
if systemctl is-active --quiet mcp.service; then
    sudo systemctl stop mcp.service
    echo -e "${GREEN}[+] MCP service stopped${NC}"
fi

# Disable MCP systemd service
echo -e "\n${BLUE}[*] Disabling MCP service...${NC}"
if systemctl is-enabled --quiet mcp.service 2>/dev/null; then
    sudo systemctl disable mcp.service
    echo -e "${GREEN}[+] MCP service disabled${NC}"
fi

# Remove MCP systemd service file
echo -e "\n${BLUE}[*] Removing MCP systemd service file...${NC}"
if [ -f /etc/systemd/system/mcp.service ]; then
    sudo rm /etc/systemd/system/mcp.service
    sudo systemctl daemon-reload
    echo -e "${GREEN}[+] MCP service file removed${NC}"
fi

# Remove MCP installation directory
echo -e "\n${BLUE}[*] Removing MCP installation...${NC}"
if [ -d /opt/mcp ]; then
    sudo rm -rf /opt/mcp
    echo -e "${GREEN}[+] MCP installation removed${NC}"
fi

# Remove CLI tools (handle symlinks or files)
echo -e "\n${BLUE}[*] Removing CLI tools...${NC}"
if [ -L /usr/local/bin/archy ] || [ -f /usr/local/bin/archy ]; then
    sudo rm -f /usr/local/bin/archy
    echo -e "${GREEN}[+] archy CLI tool removed${NC}"
fi

if [ -L /usr/local/bin/archy_chat.py ] || [ -f /usr/local/bin/archy_chat.py ]; then
    sudo rm -f /usr/local/bin/archy_chat.py
    echo -e "${GREEN}[+] archy_chat.py removed${NC}"
fi

# Remove Archy data directory (optional)
echo -e "\n${YELLOW}[*] Remove local Archy data directory? (yes/no)${NC}"
read -p ">>> " remove_data

if [[ "$remove_data" == "yes" ]]; then
    ARCHY_HOME="${ARCHY_HOME:-$HOME/.archy}"
    if [ -d "$ARCHY_HOME" ]; then
        rm -rf "$ARCHY_HOME"
        echo -e "${GREEN}[+] Data directory removed${NC}"
    fi
fi

echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}[+] Archy uninstallation complete!${NC}"
echo -e "${BLUE}========================================${NC}"

echo -e "\n${YELLOW}[*] Remaining files in current directory can be manually deleted${NC}"
echo -e "${YELLOW}[*] Git clone directory: rm -rf Archy${NC}\n"