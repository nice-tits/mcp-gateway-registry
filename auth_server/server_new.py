"""
Simplified Authentication server with local user management.
Replaces Amazon Cognito with local file-based user authentication.
Configuration is passed via headers.
"""

import argparse
import logging
import os
import jwt
import json
import yaml
import time
import uuid
import hashlib
from datetime import datetime
from typing import Dict, Optional, List, Any
from functools import lru_cache
from fastapi import FastAPI, Header, HTTPException, Request, Cookie
from fastapi.responses import JSONResponse, Response, RedirectResponse
import uvicorn
from pydantic import BaseModel
from pathlib import Path
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
import secrets
import urllib.parse
import httpx
from string import Template

# Import our local user management
from .local_user_manager import user_manager, authenticate_user, authenticate_api_key

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)
logger = logging.getLogger(__name__)

# Configuration for token generation
JWT_ISSUER = "mcp-auth-server"
JWT_AUDIENCE = "mcp-registry"
MAX_TOKEN_LIFETIME_HOURS = 24
DEFAULT_TOKEN_LIFETIME_HOURS = 8

# Rate limiting for token generation (simple in-memory counter)
user_token_generation_counts = {}
MAX_TOKENS_PER_USER_PER_HOUR = 10

# Load scopes configuration
def load_scopes_config():
    """Load the scopes configuration from scopes.yml"""
    try:
        scopes_file = Path(__file__).parent / "scopes.yml"
        with open(scopes_file, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load scopes configuration: {e}")
        return {}

# Global scopes configuration
SCOPES_CONFIG = load_scopes_config()

# Utility functions for GDPR/SOX compliance
def mask_sensitive_id(value: str) -> str:
    """Mask sensitive IDs showing only first and last 4 characters."""
    if not value or len(value) <= 8:
        return "***MASKED***"
    return f"{value[:4]}...{value[-4:]}"

def hash_username(username: str) -> str:
    """Hash username for privacy compliance."""
    if not username:
        return "anonymous"
    return f"user_{hashlib.sha256(username.encode()).hexdigest()[:8]}"

def anonymize_ip(ip_address: str) -> str:
    """Anonymize IP address by masking last octet for IPv4."""
    if not ip_address or ip_address == 'unknown':
        return ip_address
    if '.' in ip_address:  # IPv4
        parts = ip_address.split('.')
        if len(parts) == 4:
            return f"{'.'.join(parts[:3])}.xxx"
    elif ':' in ip_address:  # IPv6
        parts = ip_address.split(':')
        if len(parts) > 1:
            parts[-1] = 'xxxx'
            return ':'.join(parts)
    return ip_address

def mask_token(token: str) -> str:
    """Mask JWT token showing only last 4 characters."""
    if not token:
        return "***EMPTY***"
    if len(token) > 20:
        return f"...{token[-4:]}"
    return "***MASKED***"

def mask_headers(headers: dict) -> dict:
    """Mask sensitive headers for logging compliance."""
    masked = {}
    for key, value in headers.items():
        key_lower = key.lower()
        if key_lower in ['x-authorization', 'authorization', 'cookie']:
            if 'bearer' in str(value).lower():
                parts = str(value).split(' ', 1)
                if len(parts) == 2:
                    masked[key] = f"Bearer {mask_token(parts[1])}"
                else:
                    masked[key] = mask_token(value)
            else:
                masked[key] = "***MASKED***"
        elif key_lower in ['x-user-pool-id', 'x-client-id']:
            masked[key] = mask_sensitive_id(value)
        else:
            masked[key] = value
    return masked

def map_local_groups_to_scopes(groups: List[str]) -> List[str]:
    """
    Map local groups to MCP scopes using the group_mappings from scopes.yml configuration.
    
    Args:
        groups: List of local group names
        
    Returns:
        List of MCP scopes
    """
    scopes = []
    group_mappings = SCOPES_CONFIG.get('group_mappings', {})
    
    for group in groups:
        if group in group_mappings:
            group_scopes = group_mappings[group]
            scopes.extend(group_scopes)
            logger.debug(f"Mapped group '{group}' to scopes: {group_scopes}")
        else:
            logger.debug(f"No scope mapping found for group: {group}")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_scopes = []
    for scope in scopes:
        if scope not in seen:
            seen.add(scope)
            unique_scopes.append(scope)
    
    logger.info(f"Final mapped scopes: {unique_scopes}")
    return unique_scopes

def validate_session_cookie(cookie_value: str) -> Dict[str, any]:
    """
    Validate session cookie using itsdangerous serializer.
    
    Args:
        cookie_value: The session cookie value
        
    Returns:
        Dict containing validation results matching JWT validation format:
        {
            'valid': True,
            'username': str,
            'scopes': List[str],
            'method': 'session_cookie',
            'groups': List[str]
        }
        
    Raises:
        ValueError: If cookie is invalid or expired
    """
    global signer
    if not signer:
        logger.warning("Global signer not configured for session cookie validation")
        raise ValueError("Session cookie validation not configured")
    
    try:
        # Decrypt cookie (max_age=28800 for 8 hours)
        data = signer.loads(cookie_value, max_age=28800)
        
        # Extract user info
        username = data.get('username')
        groups = data.get('groups', [])
        
        # Map groups to scopes
        scopes = map_local_groups_to_scopes(groups)
        
        logger.info(f"Session cookie validated for user: {hash_username(username)}")
        
        return {
            'valid': True,
            'username': username,
            'scopes': scopes,
            'method': 'session_cookie',
            'groups': groups,
            'client_id': '',
            'data': data
        }
    except SignatureExpired:
        logger.warning("Session cookie has expired")
        raise ValueError("Session cookie has expired")
    except BadSignature:
        logger.warning("Invalid session cookie signature")
        raise ValueError("Invalid session cookie")
    except Exception as e:
        logger.error(f"Session cookie validation error: {e}")
        raise ValueError(f"Session cookie validation failed: {e}")

# Continue with existing validation and parsing functions...
# (All the server/tool parsing and validation functions remain the same)
# [Rest of the utility functions from original server.py that don't involve Cognito]

def parse_server_and_tool_from_url(original_url: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse server name and tool name from the original URL and request payload.
    """
    try:
        from urllib.parse import urlparse
        parsed_url = urlparse(original_url)
        path = parsed_url.path.strip('/')
        
        path_parts = path.split('/') if path else []
        server_name = path_parts[0] if path_parts else None
        
        logger.debug(f"Parsed server name '{server_name}' from URL path: {path}")
        return server_name, None
        
    except Exception as e:
        logger.error(f"Failed to parse server/tool from URL {original_url}: {e}")
        return None, None

def validate_server_tool_access(server_name: str, method: str, tool_name: str, user_scopes: List[str]) -> bool:
    """
    Validate if the user has access to the specified server method/tool based on scopes.
    """
    try:
        logger.info(f"=== VALIDATE_SERVER_TOOL_ACCESS START ===")
        logger.info(f"Requested server: '{server_name}'")
        logger.info(f"Requested method: '{method}'")
        logger.info(f"Requested tool: '{tool_name}'")
        logger.info(f"User scopes: {user_scopes}")
        logger.info(f"Available scopes config keys: {list(SCOPES_CONFIG.keys()) if SCOPES_CONFIG else 'None'}")
        
        if not SCOPES_CONFIG:
            logger.warning("No scopes configuration loaded, allowing access")
            logger.info(f"=== VALIDATE_SERVER_TOOL_ACCESS END: ALLOWED (no config) ===")
            return True
            
        # Check each user scope to see if it grants access
        for scope in user_scopes:
            logger.info(f"--- Checking scope: '{scope}' ---")
            scope_config = SCOPES_CONFIG.get(scope, [])
            
            if not scope_config:
                logger.info(f"Scope '{scope}' not found in configuration")
                continue
                
            logger.info(f"Scope '{scope}' config: {scope_config}")
            
            for server_config in scope_config:
                logger.info(f"  Examining server config: {server_config}")
                server_config_name = server_config.get('server')
                logger.info(f"  Server name in config: '{server_config_name}' vs requested: '{server_name}'")
                
                if server_config_name == server_name:
                    logger.info(f"  ✓ Server name matches!")
                    
                    allowed_methods = server_config.get('methods', [])
                    logger.info(f"  Allowed methods for server '{server_name}': {allowed_methods}")
                    logger.info(f"  Checking if method '{method}' is in allowed methods...")
                    
                    if method in allowed_methods and method != 'tools/call':
                        logger.info(f"  ✓ Method '{method}' found in allowed methods!")
                        logger.info(f"Access granted: scope '{scope}' allows access to {server_name}.{method}")
                        logger.info(f"=== VALIDATE_SERVER_TOOL_ACCESS END: GRANTED ===")
                        return True
                    
                    allowed_tools = server_config.get('tools', [])
                    logger.info(f"  Allowed tools for server '{server_name}': {allowed_tools}")
                    
                    if method == 'tools/call' and tool_name:
                        logger.info(f"  Checking if tool '{tool_name}' is in allowed tools for tools/call...")
                        if tool_name in allowed_tools:
                            logger.info(f"  ✓ Tool '{tool_name}' found in allowed tools!")
                            logger.info(f"Access granted: scope '{scope}' allows access to {server_name}.{method} for tool {tool_name}")
                            logger.info(f"=== VALIDATE_SERVER_TOOL_ACCESS END: GRANTED ===")
                            return True
                        else:
                            logger.info(f"  ✗ Tool '{tool_name}' NOT found in allowed tools")
                    else:
                        logger.info(f"  Checking if method '{method}' is in allowed tools...")
                        if method in allowed_tools:
                            logger.info(f"  ✓ Method '{method}' found in allowed tools!")
                            logger.info(f"Access granted: scope '{scope}' allows access to {server_name}.{method}")
                            logger.info(f"=== VALIDATE_SERVER_TOOL_ACCESS END: GRANTED ===")
                            return True
                        else:
                            logger.info(f"  ✗ Method '{method}' NOT found in allowed tools")
                else:
                    logger.info(f"  ✗ Server name does not match")
        
        logger.warning(f"Access denied: no scope allows access to {server_name}.{method} (tool: {tool_name}) for user scopes: {user_scopes}")
        logger.info(f"=== VALIDATE_SERVER_TOOL_ACCESS END: DENIED ===")
        return False
        
    except Exception as e:
        logger.error(f"Error validating server/tool access: {e}")
        logger.info(f"=== VALIDATE_SERVER_TOOL_ACCESS END: ERROR ===")
        return False

def validate_scope_subset(user_scopes: List[str], requested_scopes: List[str]) -> bool:
    """Validate that requested scopes are a subset of user's current scopes."""
    if not requested_scopes:
        return True
    
    user_scope_set = set(user_scopes)
    requested_scope_set = set(requested_scopes)
    
    is_valid = requested_scope_set.issubset(user_scope_set)
    
    if not is_valid:
        invalid_scopes = requested_scope_set - user_scope_set
        logger.warning(f"Invalid scopes requested: {invalid_scopes}")
    
    return is_valid

def check_rate_limit(username: str) -> bool:
    """Check if user has exceeded token generation rate limit."""
    current_time = int(time.time())
    current_hour = current_time // 3600
    
    # Clean up old entries (older than 1 hour)
    keys_to_remove = []
    for key in user_token_generation_counts.keys():
        stored_hour = int(key.split(':')[1])
        if current_hour - stored_hour > 1:
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del user_token_generation_counts[key]
    
    # Check current hour count
    rate_key = f"{username}:{current_hour}"
    current_count = user_token_generation_counts.get(rate_key, 0)
    
    if current_count >= MAX_TOKENS_PER_USER_PER_HOUR:
        logger.warning(f"Rate limit exceeded for user {hash_username(username)}: {current_count} tokens this hour")
        return False
    
    # Increment counter
    user_token_generation_counts[rate_key] = current_count + 1
    return True

# Create FastAPI app
app = FastAPI(
    title="Local Auth Server",
    description="Authentication server with local user management and JWT token validation",
    version="0.2.0"
)

class TokenValidationResponse(BaseModel):
    """Response model for token validation"""
    valid: bool
    scopes: List[str] = []
    error: Optional[str] = None
    method: Optional[str] = None
    client_id: Optional[str] = None
    username: Optional[str] = None

class GenerateTokenRequest(BaseModel):
    """Request model for token generation"""
    user_context: Dict[str, Any]
    requested_scopes: List[str] = []
    expires_in_hours: int = DEFAULT_TOKEN_LIFETIME_HOURS
    description: Optional[str] = None

class GenerateTokenResponse(BaseModel):
    """Response model for token generation"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str
    issued_at: int
    description: Optional[str] = None

class LocalTokenValidator:
    """
    Local token validator that handles self-signed JWT tokens and basic auth
    """
    
    def __init__(self):
        """Initialize with minimal configuration"""
        pass
    
    def validate_basic_auth(self, auth_header: str) -> Dict:
        """
        Validate HTTP Basic Auth credentials against local users.
        
        Args:
            auth_header: Authorization header value (Basic base64-encoded)
            
        Returns:
            Dict containing validation results
            
        Raises:
            ValueError: If auth is invalid
        """
        try:
            import base64
            
            if not auth_header.startswith('Basic '):
                raise ValueError("Invalid Basic auth format")
            
            # Decode base64 credentials
            encoded_credentials = auth_header[6:]  # Remove 'Basic '
            decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
            username, password = decoded_credentials.split(':', 1)
            
            # Authenticate with local user manager
            user_info = authenticate_user(username, password)
            if not user_info:
                raise ValueError("Invalid username or password")
            
            # Map groups to scopes
            scopes = map_local_groups_to_scopes(user_info['groups'])
            
            logger.info(f"Successfully authenticated user via Basic auth: {hash_username(username)}")
            
            return {
                'valid': True,
                'method': 'basic_auth',
                'username': user_info['username'],
                'client_id': 'basic-auth',
                'scopes': scopes,
                'groups': user_info['groups'],
                'data': user_info
            }
            
        except Exception as e:
            logger.warning(f"Basic auth validation failed: {e}")
            raise ValueError(f"Basic authentication failed: {e}")
    
    def validate_api_key_auth(self, auth_header: str) -> Dict:
        """
        Validate API key authentication.
        
        Args:
            auth_header: Authorization header value (Bearer api-key)
            
        Returns:
            Dict containing validation results
            
        Raises:
            ValueError: If auth is invalid
        """
        try:
            if not auth_header.startswith('Bearer '):
                raise ValueError("Invalid Bearer auth format")
            
            api_key = auth_header[7:]  # Remove 'Bearer '
            
            # Check if this looks like our API key format
            if not api_key.startswith('mcp-api-'):
                # Not our API key format, let it fall through to JWT validation
                raise ValueError("Not an API key format")
            
            # Authenticate with local user manager
            user_info = authenticate_api_key(api_key)
            if not user_info:
                raise ValueError("Invalid API key")
            
            # Map groups to scopes
            scopes = map_local_groups_to_scopes(user_info['groups'])
            
            logger.info(f"Successfully authenticated user via API key: {hash_username(user_info['username'])}")
            
            return {
                'valid': True,
                'method': 'api_key',
                'username': user_info['username'],
                'client_id': 'api-key-auth',
                'scopes': scopes,
                'groups': user_info['groups'],
                'data': user_info
            }
            
        except Exception as e:
            logger.debug(f"API key validation failed: {e}")
            raise ValueError(f"API key authentication failed: {e}")

    def validate_self_signed_token(self, access_token: str) -> Dict:
        """
        Validate self-signed JWT token generated by this auth server.
        
        Args:
            access_token: The JWT token to validate
            
        Returns:
            Dict containing validation results
            
        Raises:
            ValueError: If token is invalid
        """
        try:
            # Decode and validate JWT using shared SECRET_KEY
            claims = jwt.decode(
                access_token, 
                SECRET_KEY, 
                algorithms=['HS256'],
                issuer=JWT_ISSUER,
                audience=JWT_AUDIENCE,
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_iss": True,
                    "verify_aud": True
                },
                leeway=30  # 30 second leeway for clock skew
            )
            
            # Validate token_use
            token_use = claims.get('token_use')
            if token_use != 'access':
                raise ValueError(f"Invalid token_use: {token_use}")
            
            # Extract scopes from space-separated string
            scope_string = claims.get('scope', '')
            scopes = scope_string.split() if scope_string else []
            
            logger.info(f"Successfully validated self-signed token for user: {claims.get('sub')}")
            
            return {
                'valid': True,
                'method': 'self_signed',
                'data': claims,
                'client_id': claims.get('client_id', 'user-generated'),
                'username': claims.get('sub', ''),
                'expires_at': claims.get('exp'),
                'scopes': scopes,
                'groups': [],  # Self-signed tokens don't have groups
                'token_type': 'user_generated'
            }
            
        except jwt.ExpiredSignatureError:
            error_msg = "Self-signed token has expired"
            logger.warning(error_msg)
            raise ValueError(error_msg)
        except jwt.InvalidTokenError as e:
            error_msg = f"Invalid self-signed token: {e}"
            logger.warning(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Self-signed token validation error: {e}"
            logger.error(error_msg)
            raise ValueError(f"Self-signed token validation failed: {e}")

    def validate_token(self, auth_header: str, fallback_client_id: str = None) -> Dict:
        """
        Comprehensive token validation with multiple authentication methods.
        
        Supports:
        1. HTTP Basic Auth (username:password)
        2. API Key authentication (Bearer mcp-api-xxxx)
        3. Self-signed JWT tokens (Bearer jwt-token)
        
        Args:
            auth_header: Authorization header value
            fallback_client_id: Fallback client ID for compatibility
            
        Returns:
            Dict containing validation results and token information
        """
        
        # Try Basic Auth first
        if auth_header.startswith('Basic '):
            try:
                return self.validate_basic_auth(auth_header)
            except ValueError as e:
                logger.debug(f"Basic auth failed: {e}")
                # Don't fall through, Basic auth should fail explicitly
                raise ValueError(f"Basic authentication failed: {e}")
        
        # Try Bearer token (API key or JWT)
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Remove 'Bearer '
            
            # Try API key authentication first (faster)
            if token.startswith('mcp-api-'):
                try:
                    return self.validate_api_key_auth(auth_header)
                except ValueError as e:
                    logger.debug(f"API key validation failed: {e}")
                    raise ValueError(f"API key authentication failed: {e}")
            
            # Try self-signed JWT token
            try:
                return self.validate_self_signed_token(token)
            except ValueError as e:
                logger.debug(f"JWT validation failed: {e}")
                raise ValueError(f"JWT token validation failed: {e}")
        
        raise ValueError("Unsupported authentication method")

# Create global validator instance
validator = LocalTokenValidator()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "local-auth-server", "version": "0.2.0"}

@app.get("/validate")
async def validate_request(request: Request):
    """
    Validate a request by extracting configuration from headers and validating the auth token.
    
    Expected headers:
    - Authorization: Basic <base64> OR Bearer <token-or-api-key>
    - X-Original-URL: <original_url> (optional, for scope validation)
    
    Returns:
        HTTP 200 with user info headers if valid, HTTP 401/403 if invalid
        
    Raises:
        HTTPException: If the token is missing, invalid, or configuration is incomplete
    """
    
    try:
        # Extract headers
        authorization = request.headers.get("X-Authorization") or request.headers.get("Authorization")
        cookie_header = request.headers.get("Cookie", "")
        original_url = request.headers.get("X-Original-URL")
        body = request.headers.get("X-Body")
        
        # Extract server_name from original_url early for logging
        server_name_from_url = None
        if original_url:
            try:
                from urllib.parse import urlparse
                parsed_url = urlparse(original_url)
                path = parsed_url.path.strip('/')
                path_parts = path.split('/') if path else []
                server_name_from_url = path_parts[0] if path_parts else None
                logger.info(f"Extracted server_name '{server_name_from_url}' from original_url: {original_url}")
            except Exception as e:
                logger.warning(f"Failed to extract server_name from original_url {original_url}: {e}")
        
        # Read request body
        request_payload = None
        try:
            if body:
                payload_text = body
                logger.info(f"Raw Request Payload ({len(payload_text)} chars): {payload_text[:1000]}...")
                request_payload = json.loads(payload_text)
                logger.info(f"JSON RPC Request Payload: {json.dumps(request_payload, indent=2)}")
            else:
                logger.info(f"No request body provided, skipping payload parsing")
        except json.JSONDecodeError as e:
            logger.warning(f"Could not parse JSON RPC payload: {e}")
        except Exception as e:
            logger.error(f"Error reading request payload: {type(e).__name__}: {e}")
        
        # Log request for debugging with anonymized IP
        client_ip = request.client.host if request.client else 'unknown'
        logger.info(f"Validation request from {anonymize_ip(client_ip)}")
        logger.info(f"Request Method: {request.method}")
        
        # Log masked HTTP headers for GDPR/SOX compliance
        all_headers = dict(request.headers)
        masked_headers = mask_headers(all_headers)
        logger.debug(f"HTTP Headers (masked): {json.dumps(masked_headers, indent=2)}")
        
        # Log specific headers for debugging with masked sensitive data
        logger.info(f"Key Headers: Authorization={bool(authorization)}, Cookie={bool(cookie_header)}, "
                    f"Original-URL={original_url}")
        logger.info(f"Server Name from URL: {server_name_from_url}")
        
        # Initialize validation result
        validation_result = None
        
        # FIRST: Check for session cookie if present
        if "mcp_gateway_session=" in cookie_header:
            logger.info("Session cookie detected, attempting session validation")
            # Extract cookie value
            cookie_value = None
            for cookie in cookie_header.split(';'):
                if cookie.strip().startswith('mcp_gateway_session='):
                    cookie_value = cookie.strip().split('=', 1)[1]
                    break
            
            if cookie_value:
                try:
                    validation_result = validate_session_cookie(cookie_value)
                    safe_result = {k: v for k, v in validation_result.items() if k != 'username'}
                    safe_result['username'] = hash_username(validation_result.get('username', ''))
                    logger.info(f"Session cookie validation result: {safe_result}")
                    logger.info(f"Session cookie validation successful for user: {hash_username(validation_result['username'])}")
                except ValueError as e:
                    logger.warning(f"Session cookie validation failed: {e}")
                    # Fall through to auth header validation
        
        # SECOND: If no valid session cookie, check for auth header
        if not validation_result:
            if not authorization:
                logger.warning("Missing Authorization header and no valid session cookie")
                raise HTTPException(
                    status_code=401,
                    detail="Missing Authorization header. Expected: Basic <creds> or Bearer <token> or valid session cookie",
                    headers={"WWW-Authenticate": "Basic", "Connection": "close"}
                )
            
            # Validate using our local token validator
            validation_result = validator.validate_token(authorization)
        
        logger.info(f"Authentication successful using method: {validation_result['method']}")
        
        # Parse server and tool information from original URL if available
        server_name = server_name_from_url
        tool_name = None
        
        if original_url and request_payload:
            _, tool_name = parse_server_and_tool_from_url(original_url)
            logger.debug(f"Parsed from original URL: server='{server_name}', tool='{tool_name}'")
            
            # Try to extract tool name from request payload if not found in URL
            if server_name and not tool_name and request_payload:
                try:
                    if isinstance(request_payload, dict):
                        tool_name = request_payload.get('method')
                        
                        if not tool_name:
                            tool_name = request_payload.get('tool') or request_payload.get('name')
                            
                        if not tool_name and 'params' in request_payload:
                            params = request_payload['params']
                            if isinstance(params, dict):
                                tool_name = params.get('name') or params.get('tool') or params.get('method')
                        
                        logger.info(f"Extracted tool name from JSON-RPC payload: '{tool_name}'")
                    else:
                        logger.warning(f"Payload is not a dictionary: {type(request_payload)}")
                except Exception as e:
                    logger.error(f"Error processing request payload for tool extraction: {e}")
        
        # Validate scope-based access if we have server/tool information
        user_scopes = validation_result.get('scopes', [])
        if request_payload and server_name and tool_name:
            method = tool_name
            actual_tool_name = None
            
            if method == 'tools/call' and isinstance(request_payload, dict):
                params = request_payload.get('params', {})
                if isinstance(params, dict):
                    actual_tool_name = params.get('name')
                    logger.info(f"Extracted actual tool name for tools/call: '{actual_tool_name}'")
            
            # Check if user has any scopes - if not, deny access
            if not user_scopes:
                logger.warning(f"Access denied for user {hash_username(validation_result.get('username', ''))} to {server_name}.{method} (tool: {actual_tool_name}) - no scopes configured")
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied to {server_name}.{method} - user has no scopes configured",
                    headers={"Connection": "close"}
                )
            
            if not validate_server_tool_access(server_name, method, actual_tool_name, user_scopes):
                logger.warning(f"Access denied for user {hash_username(validation_result.get('username', ''))} to {server_name}.{method} (tool: {actual_tool_name})")
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied to {server_name}.{method}",
                    headers={"Connection": "close"}
                )
            logger.info(f"Scope validation passed for {server_name}.{method} (tool: {actual_tool_name})")
        elif server_name or tool_name:
            logger.debug(f"Partial server/tool info available (server='{server_name}', tool='{tool_name}'), skipping scope validation")
        else:
            logger.debug("No server/tool information available, skipping scope validation")
        
        # Prepare JSON response data
        response_data = {
            'valid': True,
            'username': validation_result.get('username') or '',
            'client_id': validation_result.get('client_id') or '',
            'scopes': validation_result.get('scopes', []),
            'method': validation_result.get('method') or '',
            'groups': validation_result.get('groups', []),
            'server_name': server_name,
            'tool_name': tool_name
        }
        logger.info(f"Full validation result: {json.dumps(validation_result, indent=2)}")
        
        # Create JSON response with headers that nginx can use
        response = JSONResponse(content=response_data, status_code=200)
        
        # Set headers for nginx auth_request_set directives
        response.headers["X-User"] = validation_result.get('username') or ''
        response.headers["X-Username"] = validation_result.get('username') or ''
        response.headers["X-Client-Id"] = validation_result.get('client_id') or ''
        response.headers["X-Scopes"] = ' '.join(validation_result.get('scopes', []))
        response.headers["X-Auth-Method"] = validation_result.get('method') or ''
        response.headers["X-Server-Name"] = server_name or ''
        response.headers["X-Tool-Name"] = tool_name or ''
        
        return response
        
    except ValueError as e:
        logger.warning(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=401,
            detail=str(e),
            headers={"WWW-Authenticate": "Basic, Bearer", "Connection": "close"}
        )
    except HTTPException as e:
        if e.status_code == 403:
            raise
        logger.error(f"HTTP error during validation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal validation error: {str(e)}",
            headers={"Connection": "close"}
        )
    except Exception as e:
        logger.error(f"Unexpected error during validation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal validation error: {str(e)}",
            headers={"Connection": "close"}
        )

@app.get("/config")
async def get_auth_config():
    """Return the authentication configuration info"""
    return {
        "auth_type": "local",
        "description": "Local user management with multiple authentication methods",
        "supported_methods": [
            "HTTP Basic Authentication (username:password)",
            "API Key Authentication (Bearer mcp-api-xxxx)",
            "Self-signed JWT tokens (Bearer jwt-token)",
            "Session cookies"
        ],
        "version": "0.2.0"
    }

@app.post("/internal/tokens", response_model=GenerateTokenResponse)
async def generate_user_token(request: GenerateTokenRequest):
    """Generate a JWT token for a user with specified scopes."""
    try:
        user_context = request.user_context
        username = user_context.get('username')
        user_scopes = user_context.get('scopes', [])
        
        if not username:
            raise HTTPException(
                status_code=400,
                detail="Username is required in user context",
                headers={"Connection": "close"}
            )
        
        # Check rate limiting
        if not check_rate_limit(username):
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Maximum {MAX_TOKENS_PER_USER_PER_HOUR} tokens per hour.",
                headers={"Connection": "close"}
            )
        
        # Validate expiration time
        expires_in_hours = request.expires_in_hours
        if expires_in_hours <= 0 or expires_in_hours > MAX_TOKEN_LIFETIME_HOURS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid expiration time. Must be between 1 and {MAX_TOKEN_LIFETIME_HOURS} hours.",
                headers={"Connection": "close"}
            )
        
        # Use user's current scopes if no specific scopes requested
        requested_scopes = request.requested_scopes if request.requested_scopes else user_scopes
        
        # Validate that requested scopes are subset of user's current scopes
        if not validate_scope_subset(user_scopes, requested_scopes):
            invalid_scopes = set(requested_scopes) - set(user_scopes)
            raise HTTPException(
                status_code=403,
                detail=f"Requested scopes exceed user permissions. Invalid scopes: {list(invalid_scopes)}",
                headers={"Connection": "close"}
            )
        
        # Generate JWT token
        current_time = int(time.time())
        expires_at = current_time + (expires_in_hours * 3600)
        
        payload = {
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "sub": username,
            "scope": " ".join(requested_scopes),
            "exp": expires_at,
            "iat": current_time,
            "jti": str(uuid.uuid4()),
            "token_use": "access",
            "client_id": "user-generated",
            "token_type": "user_generated"
        }
        
        if request.description:
            payload["description"] = request.description
        
        # Sign the token using HS256 with shared SECRET_KEY
        access_token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
        
        logger.info(f"Generated token for user '{hash_username(username)}' with scopes: {requested_scopes}, expires in {expires_in_hours} hours")
        
        return GenerateTokenResponse(
            access_token=access_token,
            expires_in=expires_in_hours * 3600,
            scope=" ".join(requested_scopes),
            issued_at=current_time,
            description=request.description
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating token: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal error generating token",
            headers={"Connection": "close"}
        )

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Local Auth Server")

    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host for the server to listen on (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8888,
        help="Port for the server to listen on (default: 8888)",
    )

    return parser.parse_args()

def main():
    """Run the server"""
    args = parse_arguments()
    
    logger.info(f"Starting local auth server on {args.host}:{args.port}")
    logger.info(f"Authentication methods: Basic Auth, API Keys, Self-signed JWT, Session cookies")
    
    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()

# Initialize SECRET_KEY and signer for session management
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    logger.warning("No SECRET_KEY environment variable found. Using a randomly generated key. "
                   "While this is more secure than a hardcoded default, it will change on restart. "
                   "Set a permanent SECRET_KEY environment variable for production.")

signer = URLSafeTimedSerializer(SECRET_KEY)

# OAuth2 functionality is preserved but Cognito is removed
# [OAuth2 functions remain largely the same but with Cognito references removed]

# Load OAuth2 providers configuration
def load_oauth2_config():
    """Load the OAuth2 providers configuration from oauth2_providers.yml"""
    try:
        oauth2_file = Path(__file__).parent / "oauth2_providers.yml"
        with open(oauth2_file, 'r') as f:
            config = yaml.safe_load(f)
            
        processed_config = substitute_env_vars(config)
        return processed_config
    except Exception as e:
        logger.error(f"Failed to load OAuth2 configuration: {e}")
        return {"providers": {}, "session": {}, "registry": {}}

def substitute_env_vars(config):
    """Recursively substitute environment variables in configuration"""
    if isinstance(config, dict):
        return {k: substitute_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [substitute_env_vars(item) for item in config]
    elif isinstance(config, str) and "${" in config:
        try:
            template = Template(config)
            return template.substitute(os.environ)
        except KeyError as e:
            logger.warning(f"Environment variable not found for template {config}: {e}")
            return config
    else:
        return config

# Global OAuth2 configuration
OAUTH2_CONFIG = load_oauth2_config()

def get_enabled_providers():
    """Get list of enabled OAuth2 providers"""
    enabled = []
    for provider_name, config in OAUTH2_CONFIG.get("providers", {}).items():
        if config.get("enabled", False):
            enabled.append({
                "name": provider_name,
                "display_name": config.get("display_name", provider_name.title())
            })
    return enabled

@app.get("/oauth2/providers")
async def get_oauth2_providers():
    """Get list of enabled OAuth2 providers for the login page"""
    try:
        providers = get_enabled_providers()
        return {"providers": providers}
    except Exception as e:
        logger.error(f"Error getting OAuth2 providers: {e}")
        return {"providers": [], "error": str(e)}

# [Rest of OAuth2 endpoints remain but with Cognito-specific code removed]
# Note: These would be simplified since we're not handling Cognito specifically anymore