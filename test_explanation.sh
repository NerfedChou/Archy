#!/bin/bash
# Test the command explanation feature

echo "Testing command explanation feature..."
echo ""
echo "Test 1: Simple command (pwd)"
archy "show me the current directory"
echo ""
echo "==================================="
echo ""
echo "Test 2: Command with flags (ls -lah)"
archy "list all files with details"

