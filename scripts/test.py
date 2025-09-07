#!/usr/bin/env python3
"""
Test runner script for MCP Gateway Registry.

This script provides a unified interface to run different types of tests
and is used by both the Makefile and GitHub Actions workflows.
"""
import sys
import subprocess
import os
from pathlib import Path

def run_command(cmd, exit_on_error=True):
    """Run a command and handle the result."""
    print(f"🔧 Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed with exit code {e.returncode}")
        if exit_on_error:
            sys.exit(e.returncode)
        return False

def check_dependencies():
    """Check if required dependencies are installed."""
    print("🔍 Checking test dependencies...")
    
    # Check if pytest is available
    try:
        import pytest
        print(f"✅ pytest {pytest.__version__} is available")
    except ImportError:
        print("❌ pytest not found. Run 'pip install -e .[dev]' first")
        return False
    
    # Check if coverage is available
    try:
        import coverage
        print(f"✅ coverage {coverage.__version__} is available")
    except ImportError:
        print("❌ coverage not found. Run 'pip install -e .[dev]' first")
        return False
    
    print("✅ All test dependencies are available")
    return True

def run_unit_tests():
    """Run unit tests."""
    print("🧪 Running unit tests...")
    return run_command([
        "python", "-m", "pytest", 
        "tests/unit/",
        "-v",
        "--tb=short",
        "-m", "unit"
    ])

def run_integration_tests():
    """Run integration tests."""
    print("🔗 Running integration tests...")
    return run_command([
        "python", "-m", "pytest", 
        "tests/integration/",
        "-v", 
        "--tb=short",
        "-m", "integration"
    ])

def run_e2e_tests():
    """Run end-to-end tests."""
    print("🌐 Running end-to-end tests...")
    return run_command([
        "python", "-m", "pytest", 
        "tests/",
        "-v", 
        "--tb=short", 
        "-m", "e2e"
    ])

def run_domain_tests(domain):
    """Run tests for a specific domain."""
    print(f"🏗️ Running {domain} domain tests...")
    return run_command([
        "python", "-m", "pytest", 
        f"tests/",
        "-v",
        "--tb=short",
        "-m", domain
    ])

def run_fast_tests():
    """Run fast tests (exclude slow tests)."""
    print("⚡ Running fast tests...")
    return run_command([
        "python", "-m", "pytest", 
        "tests/",
        "-v",
        "--tb=short",
        "-m", "not slow"
    ])

def run_all_tests():
    """Run the full test suite."""
    print("🧪 Running full test suite...")
    return run_command([
        "python", "-m", "pytest", 
        "tests/",
        "-v",
        "--tb=short"
    ])

def generate_coverage():
    """Generate coverage reports."""
    print("📊 Generating coverage reports...")
    success = run_command([
        "python", "-m", "pytest", 
        "tests/",
        "--cov=registry",
        "--cov-report=html:htmlcov",
        "--cov-report=xml:coverage.xml",
        "--cov-report=term"
    ])
    
    if success:
        print("✅ Coverage reports generated:")
        print("  - HTML: htmlcov/index.html")
        print("  - XML: coverage.xml")
    
    return success

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/test.py <command>")
        print("\nCommands:")
        print("  check        - Check test dependencies")
        print("  unit         - Run unit tests")
        print("  integration  - Run integration tests")
        print("  e2e          - Run end-to-end tests")
        print("  fast         - Run fast tests (exclude slow)")
        print("  full         - Run full test suite")
        print("  coverage     - Generate coverage reports")
        print("\nDomain commands:")
        print("  auth         - Run authentication tests")
        print("  servers      - Run server management tests")
        print("  search       - Run search tests")
        print("  health       - Run health monitoring tests")
        print("  core         - Run core infrastructure tests")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    if command == "check":
        success = check_dependencies()
    elif command == "unit":
        success = run_unit_tests()
    elif command == "integration":
        success = run_integration_tests()
    elif command == "e2e":
        success = run_e2e_tests()
    elif command == "fast":
        success = run_fast_tests()
    elif command == "full":
        success = run_all_tests()
    elif command == "coverage":
        success = generate_coverage()
    elif command in ["auth", "servers", "search", "health", "core"]:
        success = run_domain_tests(command)
    else:
        print(f"❌ Unknown command: {command}")
        success = False
    
    if not success:
        print(f"❌ Tests failed for command: {command}")
        sys.exit(1)
    else:
        print(f"✅ Tests passed for command: {command}")

if __name__ == "__main__":
    main()