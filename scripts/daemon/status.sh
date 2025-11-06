#!/bin/bash
# Check the status of the Archy Executor Daemon

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}[*] Checking Archy Executor Daemon Status...${NC}\n"

# Check systemd service first
echo -e "${BLUE}Systemd Service Status:${NC}"
if systemctl --user is-active --quiet archy-executor.service 2>/dev/null; then
    echo -e "${GREEN}✅ Service is enabled and running${NC}"
    systemctl --user status archy-executor.service --no-pager 2>/dev/null | grep -E "(Active|Memory|Tasks|CPU)" | sed 's/^/   /'
else
    echo -e "${YELLOW}⚠️  Service is not running via systemd${NC}"
fi

echo ""
echo -e "${BLUE}Process Status:${NC}"

# Check if daemon process is running
if pgrep -f "archy-executor" > /dev/null; then
    PID=$(pgrep -f "archy-executor")
    echo -e "${GREEN}✅ Daemon process is RUNNING${NC}"
    echo -e "   PID: $PID"

    # Show process info
    ps -p "$PID" -o %cpu=,%mem=,etime= 2>/dev/null | {
        read cpu mem time
        echo -e "   CPU: $cpu%"
        echo -e "   Memory: $mem%"
        echo -e "   Uptime: $time"
    }
else
    echo -e "${RED}❌ Daemon process is NOT RUNNING${NC}"
fi

echo ""
echo -e "${BLUE}Socket Status:${NC}"

# Check socket
if [ -S /tmp/archy.sock ]; then
    echo -e "${GREEN}✅ Socket is available at /tmp/archy.sock${NC}"
else
    echo -e "${RED}❌ Socket not found at /tmp/archy.sock${NC}"
fi

echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo -e "  ${YELLOW}Start:${NC}    systemctl --user start archy-executor.service"
echo -e "  ${YELLOW}Stop:${NC}     systemctl --user stop archy-executor.service"
echo -e "  ${YELLOW}Restart:${NC}  systemctl --user restart archy-executor.service"
echo -e "  ${YELLOW}Logs:${NC}     journalctl --user -u archy-executor.service -f"
echo ""

