## Python Database Model Standards

### SQLAlchemy 2.0 Conventions
- **Declarative Mapping**: Use the new `Mapped` type annotations with `mapped_column()`
- **Base Class**: Create a shared `Base` class with common columns (id, timestamps)
- **Async Sessions**: Use `async_sessionmaker` and `AsyncSession` for async database operations
- **Type Annotations**: All columns should have proper type hints for IDE support and mypy

### Model Structure
```python
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase

class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

### Naming Conventions
- **Table Names**: Use plural, snake_case names (`users`, `order_items`)
- **Column Names**: Use snake_case for all column names
- **Foreign Keys**: Name as `{referenced_table_singular}_id` (e.g., `user_id`, `order_id`)
- **Indexes**: Name with pattern `ix_{table}_{column}` or `ix_{table}_{col1}_{col2}`
- **Constraints**: Name with pattern `{table}_{column}_key` for unique, `{table}_{column}_fkey` for foreign keys

### Relationships
- **Define Both Sides**: Define relationships on both models with `back_populates`
- **Lazy Loading**: Be explicit about loading strategy (`lazy="selectin"` for async-safe eager loading)
- **Cascade Options**: Set appropriate cascade behavior (`cascade="all, delete-orphan"` where needed)
- **Nullable Foreign Keys**: Explicitly mark optional relationships with nullable foreign keys

### Queries & Sessions
- **Repository Pattern**: Encapsulate database queries in repository classes or functions
- **Session Scope**: Use dependency injection to manage session lifecycle per request
- **Select Statements**: Use `select()` statements instead of legacy `Query` API
- **Explicit Loading**: Use `selectinload()` or `joinedload()` to avoid N+1 queries

### Migrations (Alembic)
- **Autogenerate**: Use `alembic revision --autogenerate` as a starting point, then review
- **Descriptive Messages**: Use clear migration messages: `alembic revision -m "add_email_verified_to_users"`
- **Data Migrations**: Separate schema migrations from data migrations
- **Reversible Migrations**: Always implement both `upgrade()` and `downgrade()` functions
- **Test Migrations**: Test migrations in development before applying to production

### Best Practices
- **Avoid Business Logic**: Keep models focused on data structure; business logic goes in services
- **Soft Deletes**: Consider `deleted_at` timestamp instead of hard deletes for audit trails
- **Enum Columns**: Use Python Enum classes with SQLAlchemy's `Enum` type
- **JSON Columns**: Use `JSON` or `JSONB` (PostgreSQL) for flexible schema data, but prefer structured columns
