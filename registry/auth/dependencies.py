import logging
from typing import Annotated, Dict, Any

from fastapi import Depends, HTTPException, status, Cookie
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from ..core.config import settings

logger = logging.getLogger(__name__)

# Initialize session signer
signer = URLSafeTimedSerializer(settings.secret_key)


def get_current_user(
    session: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
) -> str:
    """
    Get the current authenticated user from session cookie.
    
    Returns:
        str: Username of the authenticated user
        
    Raises:
        HTTPException: If user is not authenticated
    """
    if not session:
        logger.warning("No session cookie provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        data = signer.loads(session, max_age=settings.session_max_age_seconds)
        username = data.get('username')
        
        if not username:
            logger.warning("No username found in session data")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session data"
            )
        
        logger.debug(f"Authentication successful for user: {username}")
        return username
        
    except SignatureExpired:
        logger.warning("Session cookie has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired"
        )
    except BadSignature:
        logger.warning("Invalid session cookie signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session"
        )
    except Exception as e:
        logger.error(f"Session validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


def get_user_session_data(
    session: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
) -> Dict[str, Any]:
    """
    Get the full session data for the authenticated user.
    
    Returns:
        Dict containing username, groups, auth_method, provider, etc.
        
    Raises:
        HTTPException: If user is not authenticated
    """
    if not session:
        logger.warning("No session cookie provided for session data extraction")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        data = signer.loads(session, max_age=settings.session_max_age_seconds)
        
        if not data.get('username'):
            logger.warning("No username found in session data")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session data"
            )
        
        # Set defaults for simplified authentication - all users get admin privileges
        data.setdefault('groups', ['mcp-registry-admin'])
        data.setdefault('scopes', ['mcp-servers-unrestricted/read', 'mcp-servers-unrestricted/execute'])
        
        logger.debug(f"Session data extracted for user: {data.get('username')}")
        return data
        
    except SignatureExpired:
        logger.warning("Session cookie has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired"
        )
    except BadSignature:
        logger.warning("Invalid session cookie signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session"
        )
    except Exception as e:
        logger.error(f"Session data extraction error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


def api_auth(
    session: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
) -> str:
    """
    API authentication dependency that returns the username.
    Used for API endpoints that need authentication.
    """
    return get_current_user(session)


def web_auth(
    session: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
) -> str:
    """
    Web authentication dependency that returns the username.
    Used for web pages that need authentication.
    """
    return get_current_user(session)


def enhanced_auth(
    session: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
) -> Dict[str, Any]:
    """
    Enhanced authentication dependency that returns full user context.
    Returns username with admin privileges for simplified authentication.
    """
    session_data = get_user_session_data(session)
    
    username = session_data['username']
    groups = ['mcp-registry-admin']  # All authenticated users are admins in simplified mode
    auth_method = session_data.get('auth_method', 'traditional')
    
    logger.info(f"Enhanced auth debug for {username}: groups={groups}, auth_method={auth_method}")
    
    # Simplified scopes for admin users
    scopes = ['mcp-registry-admin', 'mcp-servers-unrestricted/read', 'mcp-servers-unrestricted/execute']
    
    # UI permissions for admins (can do everything)
    ui_permissions = {
        'list_service': ['all'],
        'toggle_service': ['all'],
        'register_service': ['all']
    }
    
    # Admin users can access all servers and services
    accessible_servers = ['all']  
    accessible_services = ['all']
    
    user_context = {
        'username': username,
        'groups': groups,
        'scopes': scopes,
        'auth_method': auth_method,
        'provider': session_data.get('provider', 'local'),
        'accessible_servers': accessible_servers,
        'accessible_services': accessible_services,
        'ui_permissions': ui_permissions,
        'can_modify_servers': True,
        'is_admin': True
    }
    
    logger.debug(f"Enhanced auth context for {username}: {user_context}")
    return user_context


def create_session_cookie(username: str, auth_method: str = "traditional", provider: str = "local") -> str:
    """Create a session cookie for a user."""
    session_data = {
        "username": username,
        "auth_method": auth_method,
        "provider": provider
    }
    return signer.dumps(session_data)


def validate_login_credentials(username: str, password: str) -> bool:
    """Validate traditional login credentials."""
    return username == settings.admin_user and password == settings.admin_password


def ui_permission_required(permission: str, service_name: str = None):
    """
    Decorator to require a specific UI permission for a route.
    Since we use simplified admin-only auth, this always passes for authenticated users.
    
    Args:
        permission: The UI permission required (ignored in simplified mode)
        service_name: Optional service name (ignored in simplified mode)
    
    Returns:
        Dependency function that checks authentication
    """
    def check_permission(user_context: Dict[str, Any] = Depends(enhanced_auth)) -> Dict[str, Any]:
        # In simplified mode, all authenticated users have all permissions
        return user_context
    
    return check_permission