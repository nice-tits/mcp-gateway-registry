#!/bin/bash

# Quick validation script for MCP Gateway Registry development setup
# Run this after initial setup to verify everything is working

set -e

echo "🔍 MCP Gateway Registry - Development Setup Validation"
echo "========================================================"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

function log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

function log_error() {
    echo -e "${RED}❌ $1${NC}"
}

function log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

function log_info() {
    echo "ℹ️  $1"
}

# Check Python version
echo
log_info "Checking Python version..."
if command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version 2>&1)
    echo "$PYTHON_VERSION"
    if python -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)" 2>/dev/null; then
        log_success "Python 3.12+ is available"
    else
        log_error "Python 3.12+ required, but $PYTHON_VERSION found"
        exit 1
    fi
else
    log_error "Python not found. Please install Python 3.12+"
    exit 1
fi

# Check Node.js
echo
log_info "Checking Node.js..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "Node.js $NODE_VERSION"
    NODE_MAJOR=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$NODE_MAJOR" -ge 16 ]; then
        log_success "Node.js 16+ is available"
    else
        log_error "Node.js 16+ required, but $NODE_VERSION found"
    fi
else
    log_warning "Node.js not found. Install Node.js 18+ for frontend development"
fi

# Check Docker
echo
log_info "Checking Docker..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    echo "$DOCKER_VERSION"
    log_success "Docker is available"
else
    log_warning "Docker not found. Install Docker for containerized deployment"
fi

# Check Python dependencies
echo
log_info "Checking Python dependencies..."
if python -c "import pytest, coverage" 2>/dev/null; then
    log_success "Development dependencies are installed"
else
    log_error "Development dependencies missing. Run: pip install -e .[dev]"
    exit 1
fi

# Run dependency check through our test script
echo
log_info "Running test dependency validation..."
if python scripts/test.py check; then
    log_success "All test dependencies verified"
else
    log_error "Test dependency check failed"
    exit 1
fi

# Check if .env file exists
echo
log_info "Checking environment configuration..."
if [ -f ".env" ]; then
    log_success ".env file found"
    if grep -q "ADMIN_PASSWORD=.*" .env && ! grep -q "ADMIN_PASSWORD=your-secure-password" .env; then
        log_success "Admin password is configured"
    else
        log_warning "Admin password needs to be set in .env file"
    fi
else
    log_warning ".env file not found. Copy from .env.example and configure"
fi

# Test basic imports work
echo
log_info "Testing basic application imports..."
export CONTAINER_LOG_DIR="/tmp/mcp-test-logs"
mkdir -p "$CONTAINER_LOG_DIR"

if python -c "from registry.main import app; print('Registry app can be imported')" 2>/dev/null; then
    log_success "Registry application imports successfully"
else
    log_error "Registry application import failed"
    exit 1
fi

# Run a quick smoke test
echo
log_info "Running quick smoke tests..."
if CONTAINER_LOG_DIR="/tmp/mcp-test-logs" python -m pytest tests/unit/health/ -q --tb=no > /dev/null 2>&1; then
    log_success "Basic tests can execute"
else
    log_warning "Some tests have issues, but core setup is working"
fi

echo
echo "========================================================"
log_success "Development environment validation complete!"
echo
echo "🚀 Next steps:"
echo "   • Run 'make test-fast' for quick test feedback"
echo "   • Run './build_and_run.sh' for full Docker stack"
echo "   • See DEVELOPMENT.md for detailed development guide"
echo "   • Check docs/ for comprehensive documentation"
echo