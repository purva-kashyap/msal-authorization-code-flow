# Test Suite

This directory contains the test suite for the FastAPI SSO Authentication application.

## Running Tests

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=app --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_encryption.py
```

### Run specific test class
```bash
pytest tests/test_encryption.py::TestEncryption
```

### Run specific test
```bash
pytest tests/test_encryption.py::TestEncryption::test_encrypt_token_returns_string
```

### Run only unit tests
```bash
pytest -m unit
```

### Run with verbose output
```bash
pytest -v
```

## Test Structure

- `conftest.py` - Pytest configuration and shared fixtures
- `test_encryption.py` - Tests for encryption service
- `test_token_service.py` - Tests for token database operations
- `test_api.py` - Tests for API endpoints
- `test_config.py` - Tests for configuration
- `test_models.py` - Tests for Pydantic models

## Test Markers

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (slower, test interactions)
- `@pytest.mark.slow` - Slow running tests

## Fixtures

Common fixtures available in `conftest.py`:

- `test_settings` - Test configuration
- `test_db_session` - Test database session (SQLite in-memory)
- `test_client` - FastAPI test client
- `mock_user_data` - Mock user data
- `mock_msal_token_response` - Mock MSAL token response
- `mock_auth_flow` - Mock MSAL auth flow

## Coverage

Generate HTML coverage report:
```bash
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

## Best Practices

1. **Isolate tests** - Each test should be independent
2. **Use fixtures** - Reuse common setup via fixtures
3. **Mock external services** - Don't call real Microsoft APIs
4. **Test edge cases** - Test error conditions and boundary cases
5. **Keep tests fast** - Use in-memory database for speed
6. **Clear test names** - Test names should describe what they test

## CI/CD Integration

Add to your CI/CD pipeline:
```yaml
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest --cov=app --cov-report=xml
```
