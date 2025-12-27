
from flask import Flask
from pathlib import Path
import os
from sqlalchemy.orm import sessionmaker
from webapp.models import init_db
from webapp.services.generation_service import GenerationService

def create_app(test_config=None):
    app = Flask(__name__)
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'podcast-studio-dev-key-v2')

    # Database setup
    # We use an absolute path relative to this file to find the DB
    DB_PATH = Path(__file__).parent.parent / 'podcast_studio.db'
    engine = init_db(str(DB_PATH))
    Session = sessionmaker(bind=engine)

    # Initialize Services
    # Attach to app context so we can access it in routes
    app.gen_service = GenerationService(Session)
    app.Session = Session

    # Register Blueprints
    from webapp.routes.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    from webapp.routes.profiles import bp as profiles_bp
    app.register_blueprint(profiles_bp, url_prefix='/profiles')
    
    from webapp.routes.episodes import bp as episodes_bp
    app.register_blueprint(episodes_bp, url_prefix='/episodes')
    
    # ... more blueprints to follow ...

    return app
