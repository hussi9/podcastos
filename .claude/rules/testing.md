---
paths: tests/**/*.py
---

# Testing Requirements for PodcastOS

## Framework
- Use pytest with fixtures from conftest.py
- Test async functions with pytest.mark.asyncio
- Use pytest-cov for coverage reporting

## Coverage
- Minimum 90% coverage for critical paths
- All new features must have tests
- Edge cases and error paths must be tested

## Test Structure
```
tests/
├── unit/          # Isolated unit tests
├── integration/   # Component integration tests
├── e2e/           # End-to-end tests
└── conftest.py    # Shared fixtures
```

## Mocking
- Mock external APIs, not internal modules
- Use pytest-mock or unittest.mock
- Never mock MCP server calls in integration tests

## Running Tests
```bash
# Full test suite with coverage
/Users/airbook/devpro/podsan/venv/bin/python -m pytest tests/ -v --cov=src --cov-report=term-missing

# Specific test file
/Users/airbook/devpro/podsan/venv/bin/python -m pytest tests/unit/test_specific.py -v

# Quick smoke test
/Users/airbook/devpro/podsan/venv/bin/python -m pytest tests/ -v --tb=short -x
```
