## Python Coding Style Standards

### Code Formatting
- **Follow PEP 8**: Adhere to PEP 8 style guidelines as the baseline for all Python code
- **Line Length**: Maximum 88 characters (Black default) or 120 for projects with wider monitors
- **Formatter**: Use Black for consistent, opinionated formatting across the codebase
- **Import Sorting**: Use isort with Black-compatible profile to organize imports

### Import Organization
- **Import Order**: Standard library, third-party packages, local application imports (separated by blank lines)
- **Absolute Imports**: Prefer absolute imports over relative imports for clarity
- **No Wildcard Imports**: Never use `from module import *` - always import specific names
- **Import at Top**: All imports at the top of the file, never inside functions (except for circular import resolution)

### Type Hints
- **Type All Public APIs**: Add type hints to all public functions, methods, and class attributes
- **Use Modern Syntax**: Use `list[str]` instead of `List[str]`, `str | None` instead of `Optional[str]` (Python 3.10+)
- **TypedDict for Dicts**: Use TypedDict for dictionary structures with known keys
- **Generic Types**: Use proper generic types (`Sequence`, `Mapping`, `Iterable`) for flexible function signatures

### Naming Conventions
- **snake_case**: Functions, methods, variables, and module names
- **PascalCase**: Class names and type aliases
- **SCREAMING_SNAKE_CASE**: Constants and environment variable names
- **_single_underscore**: Private/internal names (convention, not enforced)
- **__double_underscore**: Name mangling for subclass protection (use sparingly)

### Docstrings
- **Google Style**: Use Google-style docstrings for consistency
- **Document Public APIs**: All public modules, classes, functions, and methods need docstrings
- **Args/Returns/Raises**: Document parameters, return values, and exceptions in docstrings
- **Examples**: Include usage examples in docstrings for complex functions

### Code Organization
- **Single Responsibility**: Each module, class, and function should have one clear purpose
- **Small Functions**: Keep functions focused and under 50 lines; extract helpers when needed
- **Flat Over Nested**: Avoid deep nesting; use early returns and guard clauses
- **Composition Over Inheritance**: Prefer composition and dependency injection over deep inheritance hierarchies

### Best Practices
- **Context Managers**: Use `with` statements for resource management (files, connections, locks)
- **List Comprehensions**: Use comprehensions for simple transformations; regular loops for complex logic
- **F-Strings**: Use f-strings for string formatting (not % or .format())
- **Dataclasses**: Use dataclasses or Pydantic models for data containers instead of plain dicts
- **Enums**: Use Enum classes for fixed sets of values instead of string constants
