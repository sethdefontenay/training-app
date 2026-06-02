## Python API Standards

### FastAPI-Specific Conventions
- **Pydantic Models**: Define request/response schemas as Pydantic models for automatic validation and documentation
- **Dependency Injection**: Use FastAPI's `Depends()` for database sessions, authentication, and shared logic
- **Path Operations**: Organize routes using APIRouter with meaningful prefixes and tags
- **Async by Default**: Use `async def` for route handlers; only use sync for CPU-bound operations

### Route Organization
- **Resource-Based Routing**: Group routes by resource in separate router files (`routers/users.py`, `routers/orders.py`)
- **CRUD Patterns**: Follow consistent patterns: `GET /items`, `GET /items/{id}`, `POST /items`, `PUT /items/{id}`, `DELETE /items/{id}`
- **Versioning**: Prefix API routes with version (`/api/v1/`) and use routers to manage versions

### Request/Response Handling
- **Pydantic Schemas**: Create separate schemas for Create, Update, and Response operations
- **Status Codes**: Use appropriate HTTP status codes via `status_code` parameter or `HTTPException`
- **Response Models**: Always specify `response_model` for automatic serialization and documentation
- **Pagination**: Implement cursor-based or offset pagination with consistent query parameters

### Validation
- **Pydantic Validators**: Use `@field_validator` and `@model_validator` for complex validation logic
- **Path Parameters**: Use type hints for automatic path parameter validation
- **Query Parameters**: Define query params with defaults, constraints (`gt`, `le`, `regex`)
- **Request Bodies**: Validate nested objects and lists using Pydantic models

### Authentication & Authorization
- **OAuth2 Scheme**: Use FastAPI's `OAuth2PasswordBearer` for token-based auth
- **Dependency Guards**: Create reusable dependencies for authentication checks
- **Role-Based Access**: Implement permission checks as dependencies that can be composed
- **Current User**: Use a `get_current_user` dependency pattern for authenticated routes

### Error Handling
- **HTTPException**: Raise `HTTPException` with appropriate status codes and detail messages
- **Custom Exceptions**: Define domain-specific exceptions and register exception handlers
- **Validation Errors**: Let Pydantic validation errors propagate (FastAPI handles them automatically)
- **Error Response Schema**: Use consistent error response format across all endpoints

### Documentation
- **OpenAPI Tags**: Use tags to group related endpoints in the generated documentation
- **Descriptions**: Add descriptions to routes, parameters, and schemas for clear API docs
- **Examples**: Provide example values in Pydantic models using `json_schema_extra`
- **Response Examples**: Document multiple response scenarios with different status codes
