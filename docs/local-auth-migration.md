# Local Authentication System Migration

## Overview

The MCP Gateway Registry has been migrated from Amazon Cognito to a local authentication system. This change eliminates the dependency on AWS Cognito while preserving all authentication and authorization functionality.

## Authentication Methods

### 1. HTTP Basic Authentication
For human users and simple integrations:
```bash
curl -H "Authorization: Basic $(echo -n 'username:password' | base64)" /validate
```

### 2. API Key Authentication (M2M)
For service-to-service authentication:
```bash
curl -H "Authorization: Bearer mcp-api-key-xxxxx" /validate
```

### 3. Self-Signed JWT Tokens
For extended access with specific scopes:
```bash
# Generate token
curl -X POST /internal/tokens -H "Content-Type: application/json" -d '{
  "user_context": {"username": "admin", "scopes": ["mcp-registry-admin"]},
  "requested_scopes": ["mcp-servers-unrestricted/read"],
  "expires_in_hours": 8
}'

# Use token
curl -H "Authorization: Bearer eyJ..." /validate
```

### 4. Session Cookies
Web interface authentication (unchanged from previous system).

## User Management

Users are managed in `auth_server/users.yml`. To add users:

```yaml
users:
  new_user:
    password_hash: "$2b$12$..."  # Generate with bcrypt
    groups:
      - mcp-registry-user
    enabled: true
    created_at: "2024-01-01T00:00:00Z"
    description: "New user account"
```

### Password Hash Generation
```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'password', bcrypt.gensalt()).decode())"
```

## Service Accounts

For machine-to-machine authentication:

```yaml
users:
  service_account:
    password_hash: "$2b$12$..."
    api_key: "mcp-api-key-unique-identifier"
    groups:
      - mcp-registry-service
    enabled: true
    is_service_account: true
    description: "Service account for automated access"
```

## Migration from Cognito

### Removed Environment Variables
- `COGNITO_USER_POOL_ID`
- `COGNITO_CLIENT_ID` 
- `COGNITO_CLIENT_SECRET`
- `COGNITO_DOMAIN`

### Default Credentials
- **Username**: `admin`
- **Password**: `admin`
- **API Key**: `mcp-api-key-example-12345abcdef`

**⚠️ Change these in production!**

### Group Mappings
The existing group-to-scope mapping system in `scopes.yml` is preserved:

```yaml
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

## Security Features

- **bcrypt password hashing**: Industry-standard password security
- **JWT token signing**: Cryptographically secure tokens
- **Rate limiting**: Protection against token generation abuse
- **Scope validation**: Fine-grained access control
- **GDPR-compliant logging**: Sensitive data masking

## Benefits

1. **No AWS dependency**: Completely self-contained
2. **Multiple auth methods**: Flexibility for different use cases
3. **Better M2M support**: Dedicated API key authentication
4. **Simpler deployment**: No external service configuration
5. **Cost savings**: No AWS Cognito charges

## Compatibility

- ✅ Existing web interface unchanged
- ✅ Session cookie authentication preserved  
- ✅ OAuth2 providers (GitHub, Google) still supported
- ✅ Scope-based authorization maintained
- ✅ All API endpoints compatible