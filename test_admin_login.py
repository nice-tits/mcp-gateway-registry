#!/usr/bin/env python3
"""
Simple test script to verify admin login works
"""
import sys
import os

# Add the registry directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_config():
    """Test that the configuration loads correctly"""
    try:
        from registry.core.config import settings
        print(f"✓ Config loaded successfully")
        print(f"  - Admin user: {settings.admin_user}")
        print(f"  - Admin password: {settings.admin_password}")
        print(f"  - Session cookie name: {settings.session_cookie_name}")
        return True
    except Exception as e:
        print(f"✗ Config loading failed: {e}")
        return False

def test_login_validation():
    """Test that login validation works"""
    try:
        from registry.auth.dependencies import validate_login_credentials
        
        # Test correct credentials
        if validate_login_credentials("admin", "admin"):
            print("✓ Valid admin credentials accepted")
        else:
            print("✗ Valid admin credentials rejected")
            return False
            
        # Test incorrect credentials
        if not validate_login_credentials("admin", "wrong"):
            print("✓ Invalid credentials correctly rejected")
        else:
            print("✗ Invalid credentials incorrectly accepted")
            return False
            
        if not validate_login_credentials("wrong", "admin"):
            print("✓ Invalid username correctly rejected")
        else:
            print("✗ Invalid username incorrectly accepted")
            return False
            
        return True
    except Exception as e:
        print(f"✗ Login validation test failed: {e}")
        return False

def test_session_creation():
    """Test that session creation works"""
    try:
        from registry.auth.dependencies import create_session_cookie, signer
        
        # Create a session
        session_data = create_session_cookie("admin")
        print("✓ Session cookie created successfully")
        
        # Verify we can decode it
        decoded = signer.loads(session_data, max_age=3600)
        if decoded.get("username") == "admin":
            print("✓ Session cookie can be decoded and contains correct username")
        else:
            print(f"✗ Session cookie decode failed or wrong username: {decoded}")
            return False
            
        return True
    except Exception as e:
        print(f"✗ Session creation test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing admin login functionality...")
    print("=" * 50)
    
    # Set up environment for testing
    os.environ.setdefault('ADMIN_USER', 'admin')
    os.environ.setdefault('ADMIN_PASSWORD', 'admin')
    os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing')
    
    tests = [
        test_config,
        test_login_validation,
        test_session_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        print()
        if test():
            passed += 1
        
    print()
    print("=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed! Admin login should work.")
        sys.exit(0)
    else:
        print("✗ Some tests failed. Please check the errors above.")
        sys.exit(1)