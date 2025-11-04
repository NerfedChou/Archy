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

# Setup MCP native installation
echo -e "\n${BLUE}[*] Setting up native MCP server...${NC}"
MCP_DIR="/opt/mcp"
sudo mkdir -p "$MCP_DIR"
# Use sudo rsync so files in /opt/mcp (possibly owned by root) can be updated/removed
sudo rsync -a --delete ./mcp/ "$MCP_DIR/"
# Ensure ownership so the regular user can manage the installation directory
sudo chown -R "$USER:$(id -gn)" "$MCP_DIR"

# Create Python venv for MCP
cd "$MCP_DIR"
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip --quiet
python -m pip install --only-binary :all: fastapi uvicorn pydantic requests python-dotenv --quiet
deactivate
cd -

# Create systemd service for MCP
echo -e "${BLUE}[*] Creating MCP systemd service...${NC}"
sudo tee /etc/systemd/system/mcp.service > /dev/null << 'MCPSERVICE'
[Unit]
Description=MCP Service - System Command Executor
After=network.target

[Service]
Type=simple
User=$USER
Group=$(id -gn)
WorkingDirectory=/opt/mcp
Environment="PATH=/opt/mcp/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="PYTHONPATH=/opt/mcp"
ExecStart=/opt/mcp/venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
MCPSERVICE

# Enable and start MCP service
echo -e "${BLUE}[*] Starting MCP service...${NC}"
sudo systemctl daemon-reload
sudo systemctl enable mcp.service
sudo systemctl start mcp.service

# Wait for MCP to be ready
echo -e "\n${BLUE}[*] Waiting for MCP server to be ready...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:8000/system_info/ > /dev/null 2>&1; then
        echo -e "${GREEN}[+] MCP Server is ready${NC}"
        break
    fi
    echo -n "."
    sleep 1
done


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

# Update .env if it doesn't have MCP_SERVER
echo -e "\n${BLUE}[*] Setting up environment configuration...${NC}"
if ! grep -q '^MCP_SERVER=' .env 2>/dev/null; then
    echo 'MCP_SERVER=http://localhost:8000' >> .env
    echo -e "${GREEN}[+] MCP_SERVER configuration added to .env${NC}"
fi

# Verification
echo -e "\n${BLUE}[*] Verifying installation...${NC}"
if curl -s http://localhost:8000/system_info/ > /dev/null 2>&1; then
    echo -e "${GREEN}[+] MCP Server: OK${NC}"
else
    echo -e "${YELLOW}[!] MCP Server: Not yet responding (may need a moment to start)${NC}"
fi

if systemctl is-active --quiet mcp.service; then
    echo -e "${GREEN}[+] MCP Systemd Service: Active${NC}"
else
    echo -e "${YELLOW}[!] MCP Systemd Service: Not active${NC}"
fi

echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}[+] Archy installation complete!${NC}"
echo -e "${BLUE}========================================${NC}"

echo -e "\n${GREEN}Quick Start:${NC}"
echo -e "  archy \"what is my working directory?\""
echo -e "  archy \"list the files in /home/chef\""
echo -e "  archy                    # Interactive mode"
echo -e "\n${GREEN}Service Management:${NC}"
echo -e "  systemctl status mcp.service      # Check MCP status"
echo -e "  systemctl restart mcp.service     # Restart MCP"
echo -e "  journalctl -u mcp.service -f      # View MCP logs"
echo -e "\n${GREEN}For more info: https://github.com/NerfedChou/Archy${NC}\n"