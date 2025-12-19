#!/bin/bash
# PentestAgent Docker Entrypoint

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🔧 PentestAgent Container Starting...${NC}"

# Start VPN if config provided
if [ -f "/vpn/config.ovpn" ]; then
    echo -e "${YELLOW}📡 Starting VPN connection...${NC}"
    openvpn --config /vpn/config.ovpn --daemon
    sleep 5
    
    # Check VPN connection
    if ip a show tun0 &>/dev/null; then
        echo -e "${GREEN}✅ VPN connected${NC}"
    else
        echo -e "${RED}⚠️ VPN connection may have failed${NC}"
    fi
fi

# Start Tor if enabled
if [ "$ENABLE_TOR" = "true" ]; then
    echo -e "${YELLOW}🧅 Starting Tor...${NC}"
    service tor start
    sleep 3
fi

# Initialize any databases
if [ "$INIT_METASPLOIT" = "true" ]; then
    echo -e "${YELLOW}🗄️ Initializing Metasploit database...${NC}"
    msfdb init 2>/dev/null || true
fi

# Create output directory with timestamp
OUTPUT_DIR="/output/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"
export PENTESTAGENT_OUTPUT_DIR="$OUTPUT_DIR"

echo -e "${GREEN}📁 Output directory: $OUTPUT_DIR${NC}"
echo -e "${GREEN}🚀 Starting PentestAgent...${NC}"

# Execute the main command
exec "$@"
