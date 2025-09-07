# Quick Start Guide

Get the MCP Gateway & Registry running in 5 minutes with this streamlined setup guide.

## What You'll Accomplish

By the end of this guide, you'll have:
- ✅ MCP Gateway & Registry running locally
- ✅ Local authentication system configured with default admin credentials
- ✅ AI coding assistant (VS Code) connected to the gateway
- ✅ Access to curated enterprise MCP tools

## Prerequisites

- **Docker**: Docker and Docker Compose installed
- **Basic Command Line**: Comfort with terminal/command prompt

> **No external dependencies required!** The system uses local authentication.

## Step 1: Clone and Configure

```bash
# Clone the repository
git clone https://github.com/agentic-community/mcp-gateway-registry.git
cd mcp-gateway-registry

# Copy and edit environment configuration (optional)
cp .env.example .env
```

**Edit `.env` with your values (optional - defaults work for local development):**
```bash
# Optional customizations - defaults work for local setup
ADMIN_USER=admin                    # Default: admin
ADMIN_PASSWORD=your-secure-password # Default: admin
AUTH_SERVER_URL=http://auth-server:8888
SECRET_KEY=optional-secret-key-for-sessions

# AWS Region (only needed if using other AWS services)
AWS_REGION=us-east-1
```

**Default credentials work immediately:**
- Username: `admin`
- Password: `admin`  
- API Key: `mcp-api-key-example-12345abcdef`

## Step 2: Install and Deploy

```bash
# Install Python environment (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Install Docker (Ubuntu/Debian - skip if already installed)
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo usermod -a -G docker $USER
newgrp docker

# Deploy all services
./build_and_run.sh
```

⏱️ **This takes about 2-3 minutes** - Docker will build images and start services.

> **No additional setup required!** The system uses local authentication with default credentials.

## Step 3: Verify Installation

```bash
# Check all services are running
docker-compose ps

# You should see services like:
# - registry (port 7860)  
# - auth-server (port 8888)
# - nginx (ports 80/443)
# - Various MCP servers (ports 8000-8003)
```

**Access the web interface:**
```bash
# Open in browser
open http://localhost:7860

# Or visit: http://localhost:7860
```

**Login with default credentials:**
- **Username**: `admin`
- **Password**: `admin`

**⚠️ Change these credentials in production!**

## Step 4: Connect AI Coding Assistant

### VS Code Setup (Recommended for first test)

The system generates ready-to-use configurations. For manual setup:

```bash
# Create MCP configuration for VS Code
mkdir -p ~/.vscode
cat > ~/.vscode/mcp.json << EOF
{
  "mcp": {
    "servers": {
      "mcp_gateway": {
        "url": "http://localhost:7860/mcpgw/mcp",
        "transport": "sse",
        "headers": {
          "Authorization": "Basic $(echo -n 'admin:admin' | base64)"
        }
      }
    }
  }
}
EOF
```

### Alternative: API Key Authentication

```bash
# Using API key instead of basic auth
cat > ~/.vscode/mcp.json << EOF
{
  "mcp": {
    "servers": {
      "mcp_gateway": {
        "url": "http://localhost:7860/mcpgw/mcp", 
        "transport": "sse",
        "headers": {
          "Authorization": "Bearer mcp-api-key-example-12345abcdef"
        }
      }
    }
  }
}
EOF
```

### Test the Connection

1. **Open VS Code** with MCP extension installed
2. **Open Command Palette** (`Ctrl+Shift+P` or `Cmd+Shift+P`)
3. **Run MCP command** - you should see available MCP servers
4. **Try a tool** - test with "current time" tool

### Alternative: Roo Code Setup

```bash
# For Roo Code users - using API key authentication
mkdir -p ~/.roocode
cat > ~/.roocode/mcp_servers.json << EOF
{
  "mcp_gateway": {
    "url": "http://localhost:7860/mcpgw/mcp",
    "transport": "sse", 
    "headers": {
      "Authorization": "Bearer mcp-api-key-example-12345abcdef"
    }
  }
}
EOF
```

## Step 5: Test Everything Works

```bash
# Test gateway connectivity with basic auth
curl -u admin:admin http://localhost:7860/health

# Test with API key
curl -H "Authorization: Bearer mcp-api-key-example-12345abcdef" \
  http://localhost:8888/validate

# Test MCP protocol connectivity
cd tests
./mcp_cmds.sh ping

# Should return successful ping response

# Test specific tool
./mcp_cmds.sh call currenttime current_time_by_timezone '{"tz_name": "America/New_York"}'
```

**Expected result:** Current time in New York timezone

## 🎉 Success! What's Next?

You now have a fully functional MCP Gateway & Registry! Here are your next steps:

### Immediate Next Steps
- 🔍 **Explore the Web Interface** - Browse available MCP servers and tools
- 🤖 **Try AI Assistant Integration** - Use tools through VS Code or your preferred AI assistant
- 🛠️ **Add Your Own MCP Servers** - Register custom tools for your team

### Expand Your Setup
- 📚 **[Full Installation Guide](installation.md)** - Production deployment options
- 🔐 **[Authentication Setup](auth.md)** - Advanced identity provider configuration
- 🎯 **[AI Assistants Guide](ai-coding-assistants-setup.md)** - Connect more development tools

### Enterprise Features
- 👥 **[Fine-Grained Access Control](scopes.md)** - Team-based permissions
- 📊 **[Monitoring & Analytics](monitoring.md)** - Usage tracking and health monitoring
- 🏢 **[Production Deployment](production-deployment.md)** - High availability and scaling

## Local Authentication Setup

The system uses local file-based authentication - no external services required!

### Default Configuration

The system comes with default credentials that work immediately:

**Web Interface:**
- Username: `admin`
- Password: `admin`

**API Access:**
- API Key: `mcp-api-key-example-12345abcdef`

### Customizing Authentication

#### Change Admin Password

1. **Generate Password Hash**:
```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'your_new_password', bcrypt.gensalt()).decode())"
```

2. **Update users.yml**:
```bash
# Edit auth_server/users.yml
users:
  admin:
    password_hash: "$2b$12$your_generated_hash"
    groups:
      - mcp-registry-admin
    enabled: true
```

#### Add New Users

```bash
# Add to auth_server/users.yml
users:
  newuser:
    password_hash: "$2b$12$generated_hash" 
    groups:
      - mcp-registry-user
    enabled: true
    description: "New user account"
```

#### Add Service Accounts

```bash
# Add to auth_server/users.yml  
users:
  api_service:
    password_hash: "$2b$12$generated_hash"
    api_key: "mcp-api-key-service-unique-id"
    groups:
      - mcp-registry-service
    enabled: true
    is_service_account: true
```

**For complete authentication setup:** See [Authentication Guide](auth.md)

## Troubleshooting Quick Fixes

### Services Won't Start
```bash
# Check Docker daemon
sudo systemctl status docker
sudo systemctl start docker

# Check port conflicts
sudo netstat -tlnp | grep -E ':(80|443|7860|8080)'
```

### Authentication Errors
```bash
# Test local authentication
curl -u admin:admin http://localhost:8888/validate

# Test API key authentication  
curl -H "Authorization: Bearer mcp-api-key-example-12345abcdef" \
  http://localhost:8888/validate

# Check user configuration
cat auth_server/users.yml
```

### Can't Access Web Interface
```bash
# Check if registry is running
curl http://localhost:7860/health

# Check logs
docker-compose logs registry
```

### AI Assistant Not Connecting
```bash
# Verify configuration file exists
ls -la ~/.vscode/mcp.json

# Test authentication manually
curl -u admin:admin http://localhost:7860/mcpgw/mcp

# Test with API key
curl -H "Authorization: Bearer mcp-api-key-example-12345abcdef" \
  http://localhost:7860/mcpgw/mcp
```

## Getting Help

- 📖 **[Full Documentation](/)** - Comprehensive guides and references
- 🐛 **[GitHub Issues](https://github.com/agentic-community/mcp-gateway-registry/issues)** - Bug reports and feature requests
- 💬 **[GitHub Discussions](https://github.com/agentic-community/mcp-gateway-registry/discussions)** - Community support and questions
- 📧 **[Troubleshooting Guide](troubleshooting.md)** - Common issues and detailed solutions

---

**🎯 Pro Tip:** Once you have the basic setup working, explore the [AI Coding Assistants Setup Guide](ai-coding-assistants-setup.md) to connect additional development tools like Cursor, Claude Code, and Cline for a complete enterprise AI development experience!