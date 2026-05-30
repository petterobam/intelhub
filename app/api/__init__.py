"""API Blueprint Registration"""
# Import blueprints directly to avoid module name shadowing
from app.api.tasks import bp as _tasks_bp
from app.api.crawlers import bp as _crawlers_bp
from app.api.data import bp as _data_bp
from app.api.reports import bp as _reports_bp
from app.api.health import bp as _health_bp

def register_blueprints(flaskapp):
    """Register all API blueprints on the Flask application."""
    flaskapp.register_blueprint(_tasks_bp)
    flaskapp.register_blueprint(_crawlers_bp)
    flaskapp.register_blueprint(_data_bp)
    flaskapp.register_blueprint(_reports_bp)
    flaskapp.register_blueprint(_health_bp)
