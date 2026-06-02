## Python Testing Standards

### Test Framework
- **Use pytest**: pytest is the standard for Python testing; avoid unittest-style classes
- **pytest-asyncio**: Use `pytest-asyncio` for testing async code with `@pytest.mark.asyncio`
- **Fixtures**: Use pytest fixtures for setup/teardown and dependency injection
- **Parametrize**: Use `@pytest.mark.parametrize` for testing multiple input/output combinations

### Test Organization
- **Mirror Source Structure**: Test files should mirror the source structure (`src/users/` -> `tests/users/`)
- **Test File Naming**: Name test files `test_{module}.py` to enable pytest auto-discovery
- **Test Function Naming**: Name tests `test_{function}_{scenario}` for clarity
- **Group with Classes**: Use test classes to group related tests (no `self` needed with pytest)

### Test Structure (AAA Pattern)
```python
def test_create_user_with_valid_data():
    # Arrange
    user_data = {"email": "test@example.com", "name": "Test User"}

    # Act
    result = create_user(user_data)

    # Assert
    assert result.email == "test@example.com"
    assert result.id is not None
```

### Fixtures
- **Scope Appropriately**: Use `scope="function"` (default), `"class"`, `"module"`, or `"session"` based on needs
- **Yield for Cleanup**: Use `yield` in fixtures for setup/teardown patterns
- **Factory Fixtures**: Create factory fixtures for generating test data with customizable attributes
- **Database Fixtures**: Use transaction rollback or truncation for test isolation

```python
@pytest.fixture
async def db_session():
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
def user_factory():
    def _create_user(**kwargs):
        defaults = {"email": "test@example.com", "name": "Test"}
        return User(**{**defaults, **kwargs})
    return _create_user
```

### Mocking
- **pytest-mock**: Use `pytest-mock`'s `mocker` fixture for cleaner mocking syntax
- **Mock External Services**: Always mock HTTP calls, database connections in unit tests
- **responses/httpx-mock**: Use `responses` or `httpx-mock` for mocking HTTP requests
- **Patch at Usage**: Patch where the name is used, not where it's defined

```python
def test_fetch_user_data(mocker):
    mock_response = {"id": 1, "name": "Test"}
    mocker.patch("myapp.client.httpx.get", return_value=Mock(json=lambda: mock_response))

    result = fetch_user_data(1)
    assert result["name"] == "Test"
```

### Async Testing
- **Mark Async Tests**: Use `@pytest.mark.asyncio` decorator for all async test functions
- **Async Fixtures**: Define async fixtures with `@pytest_asyncio.fixture`
- **Test Client**: Use `httpx.AsyncClient` with FastAPI's `TestClient` for API tests

```python
@pytest.mark.asyncio
async def test_async_endpoint(async_client):
    response = await async_client.get("/api/users/1")
    assert response.status_code == 200
```

### Test Categories
- **Unit Tests**: Test individual functions/classes in isolation with mocked dependencies
- **Integration Tests**: Test component interactions with real database (use test database)
- **API Tests**: Test HTTP endpoints end-to-end using test client
- **Mark Categories**: Use `@pytest.mark.integration`, `@pytest.mark.slow` to categorize tests

### Assertions
- **Plain Asserts**: Use plain `assert` statements (pytest provides detailed failure messages)
- **Assert Exceptions**: Use `pytest.raises(ExceptionType)` context manager for exception testing
- **Approximate Equality**: Use `pytest.approx()` for floating-point comparisons
- **Multiple Assertions**: Multiple assertions per test are fine if testing one logical concept

### Coverage
- **pytest-cov**: Use `pytest-cov` for coverage reporting
- **Target Coverage**: Aim for 80%+ coverage on business logic; don't chase 100% everywhere
- **Coverage Config**: Configure in `pyproject.toml` to exclude test files, migrations, etc.
- **Branch Coverage**: Enable branch coverage (`--cov-branch`) for thorough analysis
