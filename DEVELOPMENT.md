# Getting Started for Developers

Quick guide for developers who want to contribute to or develop locally with the MCP Gateway Registry.

## Prerequisites

- **Python 3.12** - Required for running the backend services
- **Node.js 18+** - Required for building the React frontend  
- **Docker & Docker Compose** - For containerized deployment
- **Git** - For version control

## Development Setup

### 1. Clone and Install Dependencies

```bash
# Clone the repository
git clone https://github.com/agentic-community/mcp-gateway-registry.git
cd mcp-gateway-registry

# Install Python development dependencies
pip install -e .[dev]

# Install frontend dependencies  
cd frontend
npm install
cd ..
```

### 2. Environment Setup

```bash
# Create local environment file
cp .env.example .env

# Edit .env to set development credentials
# Minimum required: set ADMIN_PASSWORD to something secure
```

### 3. Verify Setup

```bash
# Check if all test dependencies are installed
make check-deps

# Run fast tests to verify everything works
make test-fast

# Check code quality
make lint
```

## Development Workflows

### Testing

```bash
# Quick development tests
make test-fast

# Full test suite
make test

# Specific test categories
make test-unit         # Unit tests only
make test-integration  # Integration tests only
make test-auth         # Authentication-related tests
make test-servers      # Server management tests

# Generate coverage report
make test-coverage
```

### Code Quality

```bash
# Run linter
make lint

# Format code  
make format

# Clean up test artifacts
make clean
```

### Docker Development

```bash
# Build and run complete stack
./build_and_run.sh

# This will:
# 1. Build the React frontend
# 2. Build Docker images  
# 3. Start all services with docker-compose
# 4. Set up the registry with test data
```

## Project Structure

```
mcp-gateway-registry/
├── registry/           # Python backend (FastAPI)
├── auth_server/        # Authentication service
├── frontend/           # React frontend
├── tests/             # Test suites
├── docs/              # Documentation  
├── docker/            # Docker configurations
├── scripts/           # Utility scripts
└── .github/workflows/ # CI/CD pipelines
```

## Common Development Tasks

### Running Just the Backend

```bash
# Set environment for testing
export CONTAINER_LOG_DIR=/tmp/mcp-test-logs

# Run registry server directly
python -m uvicorn registry.main:app --reload --port 7860
```

### Running Just the Frontend

```bash
cd frontend
npm run dev
```

### Debugging Tests

```bash
# Run specific test file
python -m pytest tests/unit/health/test_health_routes.py -v

# Run with detailed output
python -m pytest tests/unit/ -v --tb=long -s

# Run tests and drop into debugger on failure
python -m pytest tests/unit/ --pdb
```

## Contributing

1. **Fork the repository** on GitHub
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes** and add tests
4. **Run the test suite**: `make test`
5. **Run code quality checks**: `make lint`
6. **Commit your changes**: `git commit -m 'Add amazing feature'`
7. **Push to the branch**: `git push origin feature/amazing-feature`
8. **Open a Pull Request**

## CI/CD Pipeline

The repository includes comprehensive GitHub Actions workflows:

- **🧪 Test Suite** - Runs on every push/PR
- **🐳 Docker Build** - Builds and tests Docker images  
- **📚 Documentation** - Deploys docs to GitHub Pages

All workflows must pass before merging PRs.

## Getting Help

- **Documentation**: [docs/](../docs/)
- **Issues**: [GitHub Issues](https://github.com/agentic-community/mcp-gateway-registry/issues)
- **Discussions**: [GitHub Discussions](https://github.com/agentic-community/mcp-gateway-registry/discussions)

## Next Steps

- Review the [Architecture Documentation](../docs/)
- Check out the [API Reference](../docs/registry_api.md)
- Explore [Example Integrations](../docs/ai-coding-assistants-setup.md)