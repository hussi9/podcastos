---
paths: src/generators/**, src/intelligence/**, src/aggregators/**
---

# Podcast Content Domain Rules

## Content Generation Standards
- All content must come from real data sources (APIs, databases, RSS feeds)
- NEVER use hardcoded or mock content
- Always validate content before publishing
- Include source attribution for aggregated content

## Generator Patterns
```python
# Required structure for all generators
class ContentGenerator:
    def __init__(self, config: GeneratorConfig):
        self.config = config
        self.logger = get_logger(__name__)

    async def generate(self, input_data: InputModel) -> OutputModel:
        """Generate content with proper error handling."""
        try:
            # Validate input
            self._validate(input_data)
            # Generate content
            result = await self._generate_impl(input_data)
            # Validate output
            return self._validate_output(result)
        except Exception as e:
            self.logger.error(f"Generation failed: {e}")
            raise
```

## Aggregator Patterns
- Use async for all I/O operations
- Implement rate limiting for external APIs
- Cache responses appropriately
- Handle API failures gracefully with retries

## Intelligence Module Standards
- Use sequential-thinking MCP for complex analysis
- Log all AI model calls for debugging
- Implement cost tracking for API usage
- Use appropriate models (haiku for simple, opus for complex)

## Data Flow
```
Sources (Reddit, RSS, Web)
    → Aggregators
    → Intelligence (Analysis/Synthesis)
    → Generators (Scripts/Newsletters)
    → Output (Audio/Text)
```

## Quality Checks
- [ ] No hardcoded content
- [ ] Error handling implemented
- [ ] Logging configured
- [ ] Async I/O used
- [ ] Rate limiting in place
- [ ] Tests written
