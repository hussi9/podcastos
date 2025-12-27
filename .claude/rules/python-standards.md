---
paths: src/**/*.py, webapp/**/*.py, tests/**/*.py
---

# Python Standards for PodcastOS

## Code Style
- Use type hints on all function signatures
- Docstrings for public APIs (Google style)
- Use dataclasses over namedtuples for data structures
- SQLAlchemy ORM for all database access
- Async/await for I/O operations

## Imports
- Standard library first, then third-party, then local
- Use absolute imports
- No wildcard imports

## Error Handling
- Use specific exception types
- Log errors with context
- Never silently swallow exceptions

## Database
- Use SQLAlchemy ORM, never raw SQL
- Always use transactions for writes
- Use connection pooling

## MCP Usage
- Use `desktop-commander` for shell operations
- Use `supabase` MCP for production database queries
- Use `sequential-thinking` for complex logic decisions
