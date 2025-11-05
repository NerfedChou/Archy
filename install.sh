#!/bin/bash

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Archy Installation Script${NC}"
echo -e "${BLUE}========================================${NC}"

# Check if running as root (not required but helps)
if [[ $EUID -eq 0 ]]; then
   echo -e "${YELLOW}[*] Running as root${NC}"
else
   echo -e "${YELLOW}[*] Running as regular user${NC}"
fi

# Check prerequisites
echo -e "\n${BLUE}[*] Checking prerequisites...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[-] Python 3 is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}[+] Python 3 found${NC}"

# Check curl
if ! command -v curl &> /dev/null; then
    echo -e "${RED}[-] curl is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}[+] curl found${NC}"

# Setup directories
echo -e "\n${BLUE}[*] Setting up directories...${NC}"
ARCHY_HOME="${ARCHY_HOME:-$HOME/.archy}"
mkdir -p "$ARCHY_HOME"
mkdir -p "$ARCHY_HOME/logs"
echo -e "${GREEN}[+] Directories created at $ARCHY_HOME${NC}"

# Make CLI script executable and install to /usr/local/bin (use symlinks to keep repo version live)
echo -e "\n${BLUE}[*] Setting up CLI tools (symlinks)...${NC}"
chmod +x scripts/archy
chmod +x scripts/archy_chat.py
# Use absolute paths so systemwide symlinks point to the repository copy
REPO_ROOT="$(pwd)"
# Remove any existing installed files first to ensure symlink replaces them
sudo rm -f /usr/local/bin/archy /usr/local/bin/archy_chat.py
sudo ln -sf "$REPO_ROOT/scripts/archy" /usr/local/bin/archy
sudo ln -sf "$REPO_ROOT/scripts/archy_chat.py" /usr/local/bin/archy_chat.py
sudo chmod +x /usr/local/bin/archy
sudo chmod +x /usr/local/bin/archy_chat.py
echo -e "${GREEN}[+] Archy CLI tools symlinked to /usr/local/bin (pointing at $REPO_ROOT/scripts)${NC}"

# Verification
echo -e "\n${BLUE}[*] Verifying installation...${NC}"
if which archy >/dev/null 2>&1; then
  echo -e "${GREEN}[+] Archy CLI: OK (${REPO_ROOT}/scripts)${NC}"
else
  echo -e "${RED}[-] Archy CLI not found on PATH${NC}"
fi

echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}[+] Archy installation complete!${NC}"
echo -e "${BLUE}========================================${NC}"

echo -e "\n${GREEN}Quick Start:${NC}"
echo -e "  archy \"what is my working directory?\""
echo -e "  archy \"list the files in /home/chef\""
echo -e "  archy                    # Interactive mode"


echo -e "\n${GREEN}For more info: https://github.com/NerfedChou/Archy${NC}\n"