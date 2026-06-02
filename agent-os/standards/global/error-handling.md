## Python Error Handling Standards

### Exception Design
- **Custom Exception Hierarchy**: Create a base exception class for your application, then specific subclasses
- **Descriptive Names**: Name exceptions clearly (`UserNotFoundError`, `InvalidTokenError`, not `Error1`)
- **Include Context**: Pass relevant context (IDs, values) to exception constructors for debugging
- **Avoid Bare Exceptions**: Never use bare `except:` - always catch specific exception types

### Exception Hierarchy Example
```python
class AppError(Exception):
    """Base exception for application errors."""
    def __init__(self, message: str, code: str | None = None):
        self.message = message
        self.code = code
        super().__init__(message)

class NotFoundError(AppError):
    """Resource not found."""
    pass

class ValidationError(AppError):
    """Input validation failed."""
    pass

class AuthenticationError(AppError):
    """Authentication failed."""
    pass
```

### Try/Except Patterns
- **Minimal Try Blocks**: Keep try blocks small; only wrap the code that might raise
- **Specific Catches**: Catch the most specific exception type possible
- **Re-raise Properly**: Use `raise` without arguments to preserve the original traceback
- **Chain Exceptions**: Use `raise NewError() from original_error` to preserve exception chain

### Logging Errors
- **Log at Boundaries**: Log errors at application boundaries (API handlers, task workers)
- **Include Context**: Log relevant identifiers, inputs, and state along with the exception
- **Use Appropriate Levels**: `logger.exception()` for unexpected errors, `logger.warning()` for handled cases
- **Structured Logging**: Use structlog or similar for machine-parseable log output

### FastAPI Error Handling
- **HTTPException**: Raise `HTTPException` for expected HTTP errors (404, 401, 403, 422)
- **Exception Handlers**: Register global exception handlers for custom exception types
- **Consistent Format**: Return errors in a consistent JSON format across all endpoints

```python
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": exc.code or "not_found", "message": exc.message}
    )
```

### Async Error Handling
- **Await Inside Try**: Place `await` calls inside try blocks to catch async errors
- **Task Exceptions**: Always handle exceptions from `asyncio.gather()` (use `return_exceptions=True` or try/except)
- **Timeout Handling**: Use `asyncio.timeout()` or `asyncio.wait_for()` with proper exception handling
- **Cleanup**: Use `finally` or async context managers for cleanup in async code

### Best Practices
- **Fail Fast**: Validate inputs early and raise exceptions immediately for invalid data
- **Don't Swallow Exceptions**: If catching an exception, either handle it meaningfully or re-raise
- **User vs Developer Messages**: Keep technical details in logs; show user-friendly messages in responses
- **Idempotent Error Handling**: Error handlers should be safe to run multiple times
