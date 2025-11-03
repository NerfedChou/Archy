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

# Stop systemd service
echo -e "\n${BLUE}[*] Stopping systemd service...${NC}"
if systemctl is-active --quiet archy; then
    sudo systemctl stop archy
    echo -e "${GREEN}[+] Service stopped${NC}"
fi

# Disable systemd service
echo -e "\n${BLUE}[*] Disabling systemd service...${NC}"
if systemctl is-enabled --quiet archy 2>/dev/null; then
    sudo systemctl disable archy
    echo -e "${GREEN}[+] Service disabled${NC}"
fi

# Remove systemd service file
echo -e "\n${BLUE}[*] Removing systemd service file...${NC}"
if [ -f /etc/systemd/system/archy.service ]; then
    sudo rm /etc/systemd/system/archy.service
    sudo systemctl daemon-reload
    echo -e "${GREEN}[+] Service file removed${NC}"
fi

# Stop and remove Docker containers
echo -e "\n${BLUE}[*] Stopping Docker containers...${NC}"
docker-compose down
echo -e "${GREEN}[+] Docker containers stopped and removed${NC}"

# Remove Docker volume
echo -e "\n${BLUE}[*] Removing Docker volumes...${NC}"
docker-compose down -v
echo -e "${GREEN}[+] Docker volumes removed${NC}"

# Remove CLI tool
echo -e "\n${BLUE}[*] Removing CLI tool...${NC}"
if [ -f /usr/local/bin/archy ]; then
    sudo rm /usr/local/bin/archy
    echo -e "${GREEN}[+] CLI tool removed${NC}"
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