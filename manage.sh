#!/bin/bash

# Archy Management Utility
# Central hub for all installation, uninstallation, and daemon management

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

show_help() {
    cat <<EOF
${BLUE}========================================${NC}
${GREEN}Archy Management Utility${NC}
${BLUE}========================================${NC}

${YELLOW}INSTALLATION:${NC}
  manage.sh install         Install Archy (build + CLI + service)
  manage.sh install-service Install/reinstall systemd service only
  manage.sh uninstall       Uninstall Archy completely
  manage.sh uninstall-service Uninstall systemd service only

${YELLOW}DAEMON MANAGEMENT:${NC}
  manage.sh daemon start    Start the Archy executor daemon
  manage.sh daemon stop     Stop the Archy executor daemon
  manage.sh daemon status   Check daemon status

${YELLOW}EXAMPLES:${NC}
  bash manage.sh install
  bash manage.sh daemon start
  bash manage.sh uninstall

${YELLOW}For more info: https://github.com/NerfedChou/Archy${NC}
EOF
}

case "$1" in
    install)
        bash "$SCRIPT_DIR/scripts/install/all.sh"
        ;;
    install-service|install-svc)
        bash "$SCRIPT_DIR/scripts/install/service.sh"
        ;;
    uninstall)
        bash "$SCRIPT_DIR/scripts/install/uninstall.sh"
        ;;
    uninstall-service|uninstall-svc)
        bash "$SCRIPT_DIR/scripts/install/uninstall-service.sh"
        ;;
    daemon)
        if [[ -z "$2" ]]; then
            echo -e "${RED}Error: daemon command requires action (start/stop/status)${NC}"
            echo -e "${YELLOW}Usage: manage.sh daemon [start|stop|status]${NC}"
            exit 1
        fi
        case "$2" in
            start)
                bash "$SCRIPT_DIR/scripts/daemon/start.sh"
                ;;
            stop)
                bash "$SCRIPT_DIR/scripts/daemon/stop.sh"
                ;;
            status)
                bash "$SCRIPT_DIR/scripts/daemon/status.sh"
                ;;
            *)
                echo -e "${RED}Unknown daemon action: $2${NC}"
                echo -e "${YELLOW}Valid actions: start, stop, status${NC}"
                exit 1
                ;;
        esac
        ;;
    help|--help|-h|"")
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac

