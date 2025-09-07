# Authentication and Authorization Guide

The MCP Gateway Registry provides enterprise-ready authentication and authorization using a local, self-contained authentication system with multiple authentication methods and fine-grained access control.

## Quick Navigation

**I want to...**
- [Set up authentication quickly](#quick-start-for-ai-agents) → Quick Start
- [Understand the authentication architecture](#authentication-architecture) → Architecture 
- [Configure user accounts and permissions](#user-management) → User Management
- [Set up automated access with API keys](#api-key-authentication) → API Keys
- [Generate JWT tokens](#jwt-token-generation) → JWT Tokens
- [See all configuration options](#configuration-reference) → Reference

---

## Quick Start for AI Agents

Get your AI agent authenticated and running in 5 minutes with the local authentication system.

### Prerequisites
- MCP Gateway Registry running (see [Quick Start](../README.md#quick-start))
- Default admin credentials (can be customized later)

### Step 1: Use Default Credentials

The system comes with default credentials that work immediately:

**For Web Interface:**
- Username: `admin`
- Password: `admin`

**For API/Programmatic Access:**
- API Key: `mcp-api-key-example-12345abcdef`
- JWT Token: Generate via web interface or API

### Step 2: Test Basic Authentication

```bash
# HTTP Basic Authentication
curl -u admin:admin http://localhost:7860/health

# API Key Authentication
curl -H "Authorization: Bearer mcp-api-key-example-12345abcdef" \
  http://localhost:8888/validate

# JWT Token (generate first via web interface)
curl -H "Authorization: Bearer eyJ..." \
  http://localhost:8888/validate
```

### Step 3: Access MCP Tools

```python
# Example: Using MCP client with local authentication
from langchain_mcp_adapters.client import MultiServerMCPClient

# Method 1: Using API Key
client = MultiServerMCPClient({
    "mcp_gateway": {
        "url": "http://localhost:7860/mcpgw/mcp",
        "transport": "sse",
        "headers": {
            "Authorization": "Bearer mcp-api-key-example-12345abcdef"
        }
    }
})

# Method 2: Using Basic Auth (base64 encoded)
import base64
auth_string = base64.b64encode(b"admin:admin").decode()
client = MultiServerMCPClient({
    "mcp_gateway": {
        "url": "http://localhost:7860/mcpgw/mcp",
        "transport": "sse", 
        "headers": {
            "Authorization": f"Basic {auth_string}"
        }
    }
})

# Discover and use tools
tools = await client.get_tools()
print(f"Available tools: {[tool['name'] for tool in tools]}")
```

### Step 4: Generate Custom JWT Token (Optional)

1. **Access Web Interface** - Login at `http://localhost:7860`
2. **Navigate to Tokens** - Go to token generation interface
3. **Configure Token** - Set expiration and scopes
4. **Copy Token** - Use in your applications

**That's it!** Your agent is now authenticated and can access MCP servers based on your assigned permissions.

---

## Authentication Architecture

### Overview

The MCP Gateway Registry uses a comprehensive local authentication system with multiple authentication methods:

1. **HTTP Basic Authentication**: Simple username/password authentication for human users and simple integrations
2. **API Key Authentication**: For service-to-service authentication and automated systems  
3. **Self-Signed JWT Tokens**: Extended access tokens with specific scopes and configurable expiration
4. **Session Cookies**: Web interface authentication with secure session management

### Key Concepts

- **Local User Management**: Users stored in `auth_server/users.yml` with bcrypt password hashing
- **Multiple Auth Methods**: Different authentication methods for different use cases
- **Group-Based Permissions**: Users assigned to groups that map to specific scopes
- **No External Dependencies**: Self-contained system with no cloud provider requirements

### High-Level Authentication Flow

```mermaid
sequenceDiagram
    participant User as User/Agent
    participant Gateway as MCP Gateway
    participant AuthServer as Auth Server
    participant LocalAuth as Local User DB<br/>(users.yml)
    
    Note over User,LocalAuth: Authentication Methods
    
    rect rgb(240, 248, 255)
        Note over User,LocalAuth: Method 1: HTTP Basic Auth
        User->>Gateway: Request with Basic auth header
        Gateway->>AuthServer: Validate credentials
        AuthServer->>LocalAuth: Check username/password
        LocalAuth->>AuthServer: User data + groups
        AuthServer->>AuthServer: Map groups to scopes
        AuthServer->>Gateway: Auth success + scopes
        Gateway->>User: Access granted
    end
    
    rect rgb(255, 248, 220)
        Note over User,LocalAuth: Method 2: API Key Auth
        User->>Gateway: Request with API key
        Gateway->>AuthServer: Validate API key
        AuthServer->>LocalAuth: Check API key
        LocalAuth->>AuthServer: Service account data
        AuthServer->>Gateway: Auth success + scopes
        Gateway->>User: Access granted
    end
    
    rect rgb(240, 255, 240)
        Note over User,LocalAuth: Method 3: JWT Token Auth
        User->>Gateway: Request with JWT token
        Gateway->>AuthServer: Validate JWT signature
        AuthServer->>AuthServer: Verify self-signed token
        AuthServer->>Gateway: Auth success + embedded scopes
        Gateway->>User: Access granted
    end
```

### Authentication Types Explained

#### HTTP Basic Authentication
- **Purpose**: Human users and simple integrations
- **Format**: `Authorization: Basic base64(username:password)`
- **Use Case**: Web interface login, simple API access
- **Credential Storage**: Bcrypt hashed passwords in users.yml

#### API Key Authentication  
- **Purpose**: Machine-to-machine authentication
- **Format**: `Authorization: Bearer mcp-api-key-xxxxx`
- **Use Case**: Service accounts, automated systems
- **Credential Storage**: API keys defined in users.yml

#### Self-Signed JWT Tokens
- **Purpose**: Extended access with specific scopes
- **Format**: `Authorization: Bearer eyJ...`
- **Use Case**: Generated tokens for specific purposes
- **Token Properties**: HMAC-SHA256 signed, configurable expiration, embedded scopes

#### Session Cookies
- **Purpose**: Web interface authentication
- **Format**: HTTP cookies with signed session data
- **Use Case**: Browser-based access to registry UI
- **Session Management**: Encrypted cookies with configurable expiration

---

## User Management

### User Configuration

Users are managed in `auth_server/users.yml`:

```yaml
users:
  # Admin user with full permissions
  admin:
    password_hash: "$2b$12$rEvb/D5urDWuuruadQrGnetnV.E5BebAVPtox1FIU1Pjkfo0OHluO"  # "admin"
    groups:
      - mcp-registry-admin
    enabled: true
    created_at: "2024-01-01T00:00:00Z"
    description: "Default administrator account"
  
  # Service account for M2M authentication
  api_service:
    password_hash: "$2b$12$..."
    api_key: "mcp-api-key-example-12345abcdef"  # For API key authentication
    groups:
      - mcp-registry-service
    enabled: true
    is_service_account: true
    description: "Service account for automated access"
```

### Adding New Users

1. **Generate Password Hash**:
```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'your_password', bcrypt.gensalt()).decode())"
```

2. **Add User to users.yml**:
```yaml
new_user:
  password_hash: "$2b$12$generated_hash"
  groups:
    - mcp-registry-user  # or other appropriate groups
  enabled: true
  created_at: "2024-01-01T00:00:00Z"
  description: "New user account"
```

3. **Optional: Add API Key for Programmatic Access**:
```yaml
new_user:
  # ... existing fields ...
  api_key: "mcp-api-key-unique-identifier"  # For API access
```

### User Groups and Permissions

Groups are mapped to scopes in `auth_server/scopes.yml`:

```yaml
group_mappings:
  # Admin users get full access
  mcp-registry-admin:
    - mcp-registry-admin
    - mcp-servers-unrestricted/read
    - mcp-servers-unrestricted/execute
  
  # Regular users get limited access
  mcp-registry-user:
    - mcp-registry-user
    - mcp-servers-restricted/read
    
  # Service accounts for automated access
  mcp-registry-service:
    - mcp-registry-service
    - mcp-servers-restricted/read
    - mcp-servers-restricted/execute
```

---

## API Key Authentication

### Setting Up API Keys

API keys provide secure machine-to-machine authentication:

```yaml
# In users.yml
service_account:
  password_hash: "$2b$12$..."  # Still needed for potential basic auth
  api_key: "mcp-api-key-production-xyz789"
  groups:
    - mcp-registry-service
  enabled: true
  is_service_account: true
```

### Using API Keys

```bash
# Direct API access
curl -H "Authorization: Bearer mcp-api-key-production-xyz789" \
  http://localhost:8888/validate

# MCP client configuration
export MCP_API_KEY="mcp-api-key-production-xyz789"
```

### API Key Security Best Practices

1. **Unique Keys**: Each service account should have a unique API key
2. **Descriptive Names**: Use descriptive suffixes (`mcp-api-key-service-name-env`)
3. **Regular Rotation**: Rotate API keys periodically
4. **Scope Limitation**: Assign minimal required permissions
5. **Secure Storage**: Store keys in secure configuration management

---

## JWT Token Generation

### Web Interface Token Generation

1. **Login to Web Interface** at `http://localhost:7860`
2. **Navigate to Token Management** (if available in UI)
3. **Configure Token Parameters**:
   - Description (optional)
   - Expiration time (1-24 hours)
   - Custom scopes (subset of your permissions)
4. **Generate and Copy Token**

### Programmatic Token Generation

```bash
# Generate token via API (requires authentication)
curl -X POST http://localhost:8888/internal/tokens \
  -H "Authorization: Basic $(echo -n 'admin:admin' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "requested_scopes": ["mcp-servers-restricted/read"],
    "expires_in_hours": 8,
    "description": "Agent access token"
  }'
```

### Using JWT Tokens

```python
# In your agent code
headers = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}

client = MultiServerMCPClient({
    "mcp_gateway": {
        "url": "http://localhost:7860/mcpgw/mcp",
        "transport": "sse",
        "headers": headers
    }
})
```

### JWT Token Properties

- **Algorithm**: HMAC-SHA256
- **Issuer**: `mcp-auth-server`
- **Audience**: `mcp-registry`
- **Expiration**: 1-24 hours (configurable)
- **Scopes**: Embedded in token, validated on each request
- **Unique ID**: Each token has a unique `jti` claim

## Fine-Grained Access Control (FGAC)

The FGAC system provides granular permissions for MCP servers, methods, and individual tools using the same proven scope system.

### Key Concepts

#### Scope Types

- **UI Scopes**: Registry management permissions
  - `mcp-registry-admin`: Full administrative access
  - `mcp-registry-user`: Limited user access
  
- **Server Scopes**: MCP server access
  - `mcp-servers-unrestricted/read`: Read all servers
  - `mcp-servers-unrestricted/execute`: Execute all tools
  - `mcp-servers-restricted/read`: Limited read access
  - `mcp-servers-restricted/execute`: Limited execute access

#### Methods vs Tools

The system distinguishes between:

- **MCP Methods**: Protocol operations (`initialize`, `tools/list`, `tools/call`)
- **Individual Tools**: Specific functions within servers

### Access Control Example

```yaml
# User can list tools but only execute specific ones
mcp-servers-restricted/execute:
  - server: fininfo
    methods:
      - tools/list        # Can list all tools
      - tools/call        # Can call tools
    tools:
      - get_stock_aggregates   # But only these specific tools
      - print_stock_data       # Not other tools in the server
```

### Common Scenarios

| Scenario | Can List Tools? | Can Execute? | Which Tools? |
|----------|----------------|--------------|--------------|
| Read-only user | ✅ Yes | ❌ No | N/A |
| Restricted execute | ✅ Yes | ✅ Yes | Only specified tools |
| Unrestricted admin | ✅ Yes | ✅ Yes | All tools |

For complete FGAC documentation, see [Fine-Grained Access Control](scopes.md).

---

## Configuration Reference

📋 **For complete configuration documentation, see [Configuration Reference](configuration.md)**

### Key Configuration Files

| Configuration | Location | Purpose |
|---------------|----------|---------|
| **Main Environment** | `.env` | Core project settings and registry URLs |
| **User Management** | `auth_server/users.yml` | Local user accounts, passwords, and API keys |
| **Permissions** | `auth_server/scopes.yml` | Group-to-scope mappings and access control |

### Quick Configuration

#### Main Environment Configuration

```bash
# .env file (minimal configuration)
ADMIN_USER=admin
ADMIN_PASSWORD=your-secure-password
AUTH_SERVER_URL=http://auth-server:8888
AUTH_SERVER_EXTERNAL_URL=https://your-domain.com
SECRET_KEY=your-secret-key-here
```

#### User Management Configuration

```yaml
# auth_server/users.yml
users:
  admin:
    password_hash: "$2b$12$..."  # bcrypt hash
    groups:
      - mcp-registry-admin
    enabled: true
    
  api_service:
    password_hash: "$2b$12$..."
    api_key: "mcp-api-key-service-12345"
    groups:
      - mcp-registry-service
    enabled: true
    is_service_account: true
```

#### Permissions Configuration

```yaml
# auth_server/scopes.yml
group_mappings:
  mcp-registry-admin:
    - mcp-registry-admin
    - mcp-servers-unrestricted/read
    - mcp-servers-unrestricted/execute

  mcp-registry-service:
    - mcp-registry-service
    - mcp-servers-restricted/read
    - mcp-servers-restricted/execute
```

---

## Security Considerations

### Best Practices

1. **Strong Passwords**: Use strong passwords and change defaults in production
2. **API Key Security**: Generate unique API keys and store them securely
3. **Token Expiration**: Use appropriate JWT token expiration times
4. **Scope Limitation**: Follow principle of least privilege
5. **Regular Updates**: Regularly review and update user permissions

### Authentication Security Features

- **bcrypt Password Hashing**: Industry-standard password security with configurable rounds
- **HMAC-SHA256 JWT Signing**: Cryptographically secure token signing
- **Secure Session Management**: Encrypted session cookies with expiration
- **Rate Limiting**: Protection against brute force attacks
- **GDPR-Compliant Logging**: Sensitive data masking in logs

### Token Lifecycle

- **JWT tokens**: 1-24 hour configurable expiry
- **Session cookies**: Configurable expiration (default 8 hours)
- **API keys**: Long-lived but can be rotated as needed
- **Password-based auth**: Immediate validation, no token persistence

---

## Troubleshooting

### Common Issues

**Authentication fails with valid credentials**
- Verify user exists in `users.yml` and is enabled
- Check password hash is correct (regenerate if needed)
- Ensure auth server is running and accessible

**API key authentication not working**
- Verify API key format: `mcp-api-key-xxxxx`
- Check API key exists in users.yml for the user
- Ensure user has appropriate groups assigned

**JWT token validation fails**
- Verify token hasn't expired
- Check SECRET_KEY is consistent across restarts
- Ensure token was generated by the same auth server

**Permissions denied for specific tools**
- Check user's group memberships in users.yml
- Verify group-to-scope mappings in scopes.yml
- Ensure scope definitions include the requested tools

---

## Testing and Validation

### Authentication Testing

```bash
# Test HTTP Basic Authentication
curl -u admin:admin http://localhost:8888/validate

# Test API Key Authentication
curl -H "Authorization: Bearer mcp-api-key-example-12345abcdef" \
  http://localhost:8888/validate

# Test JWT Token (generate token first)
curl -H "Authorization: Bearer eyJ..." \
  http://localhost:8888/validate

# Test MCP Gateway connectivity
curl -u admin:admin http://localhost:7860/health
```

### User Management Testing

```bash
# Test user creation (add to users.yml first)
python -c "
from auth_server.local_user_manager import user_manager
user = user_manager.get_user('testuser')
print(f'User: {user}')
"

# Test password validation
python -c "
from auth_server.local_user_manager import user_manager
result = user_manager.authenticate_user('admin', 'admin')
print(f'Auth result: {result}')
"
```

### Permission Testing

Use the MCP testing tools to validate permissions:

```bash
# Test basic connectivity
./tests/mcp_cmds.sh ping

# Test tool listing (filtered by permissions)
./tests/mcp_cmds.sh list

# Test specific tool execution
./tests/mcp_cmds.sh call currenttime current_time_utc '{}'
```

---

## Migration from Cognito

If you're migrating from a previous Cognito-based setup, see [Local Authentication Migration](local-auth-migration.md) for detailed migration instructions.

### Key Changes

1. **No AWS Dependencies**: Amazon Cognito completely removed
2. **Local User Management**: Users managed in YAML files
3. **Multiple Auth Methods**: Basic auth, API keys, and JWT tokens
4. **Simplified Setup**: No external service configuration required
5. **Backwards Compatibility**: Existing scope and permission systems preserved

### Benefits of Local Authentication

- **Zero External Dependencies**: No cloud provider accounts required
- **Simplified Deployment**: No complex OAuth provider setup
- **Better Development Experience**: Immediate setup with default credentials
- **Cost Savings**: No external authentication service costs
- **Enhanced Security**: Self-contained system with no external attack vectors

---

## Additional Resources

- [Complete Configuration Reference](configuration.md)
- [Fine-Grained Access Control Documentation](scopes.md)
- [User Management Examples](../auth_server/users.yml)
- [MCP Testing Tools](../tests/mcp_cmds.sh)
- [Source: Auth Server Implementation](../auth_server/server.py)