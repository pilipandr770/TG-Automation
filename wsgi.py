"""
WSGI entry point for Gunicorn (Production)

This file is used by Render.com and other WSGI servers.
For local development, use: python run.py
"""
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

from app import create_app

app = create_app()

if __name__ == '__main__':
    # This is only for local testing
    # For production, use: gunicorn wsgi:app
    logger.warning('Running in development mode. For production use gunicorn.')
    app.run(host='0.0.0.0', port=5000, debug=False)
