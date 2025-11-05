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
echo -e "\n${YELLOW}[!] This will remove Archy CLI and optional data${NC}"
echo -e "${YELLOW}[!] Continue? (yes/no)${NC}"
read -p ">>> " confirm

if [[ "$confirm" != "yes" ]]; then
    echo -e "${YELLOW}[*] Uninstallation cancelled${NC}"
    exit 0
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

# Clean up any leftover MCP artifacts just in case (legacy)
if systemctl list-units --type=service --all | grep -q "mcp.service"; then
    echo -e "\n${YELLOW}[!] Legacy MCP service detected, removing...${NC}"
    sudo systemctl stop mcp.service || true
    sudo systemctl disable mcp.service || true
    sudo rm -f /etc/systemd/system/mcp.service || true
    sudo systemctl daemon-reload || true
fi
if [ -d /opt/mcp ]; then
    sudo rm -rf /opt/mcp
fi

echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}[+] Archy uninstallation complete!${NC}"
echo -e "${BLUE}========================================${NC}"

echo -e "\n${YELLOW}[*] Remaining files in current directory can be manually deleted${NC}"
echo -e "${YELLOW}[*] Git clone directory: rm -rf Archy${NC}\n"