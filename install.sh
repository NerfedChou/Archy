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

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}[-] Docker is not installed${NC}"
    echo -e "${YELLOW}[*] Install Docker first: https://docs.docker.com/engine/install/arch/${NC}"
    exit 1
fi
echo -e "${GREEN}[+] Docker found${NC}"

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}[-] Docker Compose is not installed${NC}"
    echo -e "${YELLOW}[*] Install Docker Compose: sudo pacman -S docker-compose${NC}"
    exit 1
fi
echo -e "${GREEN}[+] Docker Compose found${NC}"

# Check if user can run docker
if ! docker ps &> /dev/null; then
    echo -e "${RED}[-] Cannot run Docker (permission denied)${NC}"
    echo -e "${YELLOW}[*] Add your user to docker group: sudo usermod -aG docker $USER${NC}"
    exit 1
fi
echo -e "${GREEN}[+] Docker permissions OK${NC}"

# Setup directories
echo -e "\n${BLUE}[*] Setting up directories...${NC}"
ARCHY_HOME="${ARCHY_HOME:-$HOME/.archy}"
mkdir -p "$ARCHY_HOME"
mkdir -p "$ARCHY_HOME/ollama"
mkdir -p "$ARCHY_HOME/logs"
echo -e "${GREEN}[+] Directories created at $ARCHY_HOME${NC}"

# Build Docker image
echo -e "\n${BLUE}[*] Building Docker image...${NC}"
docker-compose build
echo -e "${GREEN}[+] Docker image built${NC}"

# Start services
echo -e "\n${BLUE}[*] Starting Archy services...${NC}"
docker-compose up -d
echo -e "${GREEN}[+] Services started${NC}"

# Wait for services to be ready
echo -e "\n${BLUE}[*] Waiting for services to be ready (this may take a minute)...${NC}"
for i in {1..60}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}[+] MCP Server is ready${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

# Pull Ollama model
echo -e "\n${BLUE}[*] Pulling Mistral model (this may take a few minutes)...${NC}"
docker exec archy-ollama ollama pull mistral
echo -e "${GREEN}[+] Mistral model pulled${NC}"

# Make CLI script executable
echo -e "\n${BLUE}[*] Setting up CLI...${NC}"
chmod +x scripts/archy
sudo cp scripts/archy /usr/local/bin/archy
echo -e "${GREEN}[+] Archy CLI installed to /usr/local/bin/archy${NC}"

# Create systemd service for auto-start (optional)
echo -e "\n${BLUE}[*] Setting up auto-start...${NC}"
ARCHY_PATH="$(pwd)"
sudo tee /etc/systemd/system/archy.service > /dev/null <<EOF
[Unit]
Description=Archy - Local AI Assistant
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=$ARCHY_PATH
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
RemainAfterExit=yes
User=$USER

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable archy.service
echo -e "${GREEN}[+] Systemd service created and enabled${NC}"

# Verification
echo -e "\n${BLUE}[*] Verifying installation...${NC}"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}[+] MCP Server: OK${NC}"
else
    echo -e "${RED}[-] MCP Server: FAILED${NC}"
fi

if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}[+] Ollama: OK${NC}"
else
    echo -e "${RED}[-] Ollama: FAILED${NC}"
fi

echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}[+] Archy installation complete!${NC}"
echo -e "${BLUE}========================================${NC}"

echo -e "\n${GREEN}Quick Start:${NC}"
echo -e "  archy \"update my system\""
echo -e "  archy \"what tools are installed?\""
echo -e "  archy sysinfo"
echo -e "\n${GREEN}Service Management:${NC}"
echo -e "  systemctl start archy"
echo -e "  systemctl stop archy"
echo -e "  systemctl status archy"
echo -e "\n${GREEN}View Logs:${NC}"
echo -e "  docker-compose logs -f"
echo -e "\n${GREEN}For more info: https://github.com/NerfedChou/Archy${NC}\n"