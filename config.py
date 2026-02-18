import os
from dotenv import load_dotenv

load_dotenv()

# Deployment: 2026-02-18 21:42 - CSRF token fixes

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max upload

    # SQLAlchemy engine options
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,  # Test connections before using them
        'pool_recycle': 3600,   # Recycle connections after 1 hour
    }

    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

    # Telegram
    TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
    TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
    TELEGRAM_PHONE = os.getenv('TELEGRAM_PHONE')
    TELEGRAM_TARGET_CHANNEL = os.getenv('TELEGRAM_TARGET_CHANNEL')

    # Redis
    REDIS_URL = os.getenv('REDIS_URL')


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///telegram_automation.db')


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')

    @staticmethod
    def init_app(app):
        # Fix Render.com postgres:// → postgresql://
        uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if uri and uri.startswith('postgres://'):
            uri = uri.replace('postgres://', 'postgresql://', 1)
        
        # Ensure psycopg driver is explicitly set (for psycopg2-binary compatibility)
        if uri and uri.startswith('postgresql://') and '+psycopg' not in uri:
            uri = uri.replace('postgresql://', 'postgresql+psycopg://', 1)
        
        # Add proper SSL settings to prevent certificate errors (sslmode=prefer allows both SSL and non-SSL)
        if uri and 'sslmode' not in uri:
            # Check if URL already has query parameters
            if '?' in uri:
                uri += '&sslmode=prefer'
            else:
                uri += '?sslmode=prefer'
        
        if uri:
            app.config['SQLALCHEMY_DATABASE_URI'] = uri


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
