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

# Uninstall systemd service if present
echo -e "\n${BLUE}[*] Uninstalling systemd service...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if bash "$SCRIPT_DIR/uninstall-service.sh"; then
    echo -e "${GREEN}[+] Systemd service removed${NC}"
fi

# Kill any remaining daemon processes
pkill -f "archy-executor" 2>/dev/null || true
rm -f /tmp/archy.sock 2>/dev/null || true

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
# Use absolute paths so systemwide symlinks point to the repository copy
REPO_ROOT="$(pwd)"
# Remove any existing installed files first to ensure symlink replaces them
sudo rm -f /usr/local/bin/archy /usr/local/bin/archy_chat.py /usr/local/bin/rust_executor.py
sudo ln -sf "$REPO_ROOT/scripts/archy" /usr/local/bin/archy
sudo ln -sf "$REPO_ROOT/scripts/archy_chat.py" /usr/local/bin/archy_chat.py
sudo ln -sf "$REPO_ROOT/scripts/rust_executor.py" /usr/local/bin/rust_executor.py
sudo chmod +x /usr/local/bin/archy
sudo chmod +x /usr/local/bin/archy_chat.py
echo -e "${GREEN}[+] Archy CLI tools symlinked to /usr/local/bin (pointing at $REPO_ROOT/scripts)${NC}"

# Install systemd service
echo -e "\n${BLUE}[*] Installing systemd service...${NC}"
if bash "$REPO_ROOT/scripts/install/service.sh"; then
    echo -e "${GREEN}[+] Systemd service installed and started${NC}"
else
    echo -e "${YELLOW}[!] Failed to install systemd service (you can do this manually later)${NC}"
    echo -e "${YELLOW}[!] Run: bash $REPO_ROOT/scripts/install/service.sh${NC}"
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

