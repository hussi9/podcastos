---
paths: src/app/**, webapp/**
---

# API Integration Rules

## FastAPI Patterns (src/app/)
```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["resource"])

class ResourceCreate(BaseModel):
    """Always use Pydantic models for request/response."""
    name: str
    config: dict

@router.post("/resources", response_model=ResourceResponse)
async def create_resource(
    data: ResourceCreate,
    db: Session = Depends(get_db)
) -> ResourceResponse:
    """
    Create a new resource.

    Always include:
    - Type hints
    - Docstrings
    - Error handling
    """
    try:
        resource = await ResourceService.create(db, data)
        return ResourceResponse.from_orm(resource)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create resource: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

## Flask Patterns (webapp/)
```python
from flask import Blueprint, jsonify, request
from webapp.models import db

bp = Blueprint('resource', __name__, url_prefix='/api')

@bp.route('/resources', methods=['POST'])
def create_resource():
    """Create resource with proper error handling."""
    try:
        data = request.get_json()
        # Validate
        if not data.get('name'):
            return jsonify({'error': 'Name required'}), 400
        # Create
        resource = Resource(**data)
        db.session.add(resource)
        db.session.commit()
        return jsonify(resource.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
```

## Security Requirements
- Validate all input data
- Use parameterized queries (ORM)
- Implement rate limiting
- Log security-relevant events
- Never expose internal errors to clients

## Response Standards
- Use consistent response format
- Include pagination for lists
- Return appropriate HTTP status codes
- Include request IDs for debugging
