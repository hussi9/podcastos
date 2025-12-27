---
paths: webapp/models.py, src/**/*repository*.py, src/**/*db*.py
---

# Database Rules for PodcastOS

## SQLAlchemy ORM Patterns

### Model Definition
```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class Episode(Base):
    __tablename__ = 'episodes'

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    host_id = Column(Integer, ForeignKey('hosts.id'))

    # Relationships with lazy loading strategy
    host = relationship("Host", back_populates="episodes", lazy="joined")

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'created_at': self.created_at.isoformat(),
            'host': self.host.to_dict() if self.host else None
        }
```

### Query Patterns
```python
# GOOD: Eager loading to avoid N+1
episodes = db.query(Episode).options(
    joinedload(Episode.host),
    joinedload(Episode.topics)
).filter(Episode.status == 'published').all()

# GOOD: Pagination
def get_paginated(page: int, per_page: int = 20):
    return db.query(Episode)\
        .order_by(Episode.created_at.desc())\
        .offset((page - 1) * per_page)\
        .limit(per_page)\
        .all()

# BAD: N+1 query
for episode in episodes:
    print(episode.host.name)  # Triggers separate query each time
```

### Transaction Management
```python
# Always use context managers
def create_episode(data: dict) -> Episode:
    try:
        episode = Episode(**data)
        db.session.add(episode)
        db.session.commit()
        return episode
    except Exception as e:
        db.session.rollback()
        raise

# For multiple operations
def bulk_create(items: list) -> list:
    try:
        db.session.bulk_save_objects(items)
        db.session.commit()
        return items
    except Exception:
        db.session.rollback()
        raise
```

## MCP Database Access
When supabase MCP is available, prefer it over direct SQLite:
```
Use supabase to query episodes where status = 'published' limit 10
Use supabase to insert into episodes (title, host_id) values ('New Episode', 1)
```

## Database Files
- Development: `/Users/airbook/devpro/podsan/podcast_studio.db`
- Webapp copy: `/Users/airbook/devpro/podsan/webapp/podcast_studio.db`

## Quick Commands
```bash
# View tables
sqlite3 podcast_studio.db ".tables"

# View schema
sqlite3 podcast_studio.db ".schema episodes"

# Quick query
sqlite3 podcast_studio.db "SELECT COUNT(*) FROM episodes;"
```
