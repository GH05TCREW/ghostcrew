#!/bin/bash
# GhostCrew Setup Script

set -e

echo "=================================================================="
echo "                        GHOSTCREW"
echo "                  AI Penetration Testing"
echo "=================================================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.10"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "Error: Python $required_version or higher is required (found $python_version)"
    exit 1
fi
echo "[OK] Python $python_version"

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "[OK] Virtual environment created"
else
    echo "[OK] Virtual environment exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -e ".[all]"
echo "[OK] Dependencies installed"

# Install playwright browsers
echo "Installing Playwright browsers..."
playwright install chromium
echo "[OK] Playwright browsers installed"

# Create .env file if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << EOF
# GhostCrew Configuration
# Add your API keys here

# OpenAI API Key (required for GPT models)
OPENAI_API_KEY=

# Anthropic API Key (required for Claude models)
ANTHROPIC_API_KEY=

# Model Configuration
GHOSTCREW_MODEL=gpt-5

# Debug Mode
GHOSTCREW_DEBUG=false

# Max Iterations
GHOSTCREW_MAX_ITERATIONS=50
EOF
    echo "[OK] .env file created"
    echo "[!] Please edit .env and add your API keys"
fi

# Create loot directory for reports
mkdir -p loot
echo "[OK] Loot directory created"

echo ""
echo "=================================================================="
echo "Setup complete!"
echo ""
echo "To get started:"
echo "  1. Edit .env and add your API keys"
echo "  2. Activate the virtual environment: source venv/bin/activate"
echo "  3. Run GhostCrew: ghostcrew or python -m ghostcrew"
echo ""
echo "For Docker usage:"
echo "  docker-compose up ghostcrew"
echo "  docker-compose --profile kali up ghostcrew-kali"
echo ""
echo "=================================================================="
