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
# Check Rust
if ! command -v cargo &> /dev/null; then
    echo -e "${RED}[-] Rust/Cargo is not installed${NC}"
    echo -e "${YELLOW}[*] Install with: sudo pacman -S rust${NC}"
    exit 1
fi
echo -e "${GREEN}[+] Rust/Cargo found${NC}"
# Check tmux
if ! command -v tmux &> /dev/null; then
    echo -e "${YELLOW}[!] tmux not found (optional but recommended)${NC}"
fi
# Check foot
if ! command -v foot &> /dev/null; then
    echo -e "${YELLOW}[!] foot terminal not found (optional but recommended)${NC}"
fi
# Setup directories
echo -e "\n${BLUE}[*] Setting up directories...${NC}"
ARCHY_HOME="${ARCHY_HOME:-$HOME/.archy}"
mkdir -p "$ARCHY_HOME"
mkdir -p "$ARCHY_HOME/logs"
echo -e "${GREEN}[+] Directories created at $ARCHY_HOME${NC}"
# Build Rust executor
echo -e "\n${BLUE}[*] Building Rust executor daemon...${NC}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
if cargo build --release; then
    echo -e "${GREEN}[+] Rust executor built successfully${NC}"
else
    echo -e "${RED}[-] Failed to build Rust executor${NC}"
    exit 1
fi
# Make CLI script executable and install to /usr/local/bin (use symlinks to keep repo version live)
echo -e "\n${BLUE}[*] Setting up CLI tools (symlinks)...${NC}"
chmod +x scripts/archy
chmod +x scripts/archy_chat.py
# Remove any existing installed files first to ensure symlink replaces them
sudo rm -f /usr/local/bin/archy /usr/local/bin/archy_chat.py /usr/local/bin/rust_executor.py
sudo ln -sf "$REPO_ROOT/scripts/archy" /usr/local/bin/archy
sudo ln -sf "$REPO_ROOT/scripts/archy_chat.py" /usr/local/bin/archy_chat.py
sudo ln -sf "$REPO_ROOT/scripts/rust_executor.py" /usr/local/bin/rust_executor.py
sudo chmod +x /usr/local/bin/archy
sudo chmod +x /usr/local/bin/archy_chat.py
echo -e "${GREEN}[+] Archy CLI tools symlinked to /usr/local/bin${NC}"
# Install systemd service
echo -e "\n${BLUE}[*] Installing systemd service...${NC}"
if bash "$REPO_ROOT/scripts/install/service.sh"; then
    echo -e "${GREEN}[+] Systemd service installed and started${NC}"
else
    echo -e "${YELLOW}[!] Failed to install systemd service${NC}"
    echo -e "${YELLOW}[!] You can retry with: bash $REPO_ROOT/scripts/install/service.sh${NC}"
fi
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
