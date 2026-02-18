from app import create_app, db
import os

# Remove old database
if os.path.exists('./instance/telegram_automation.db'):
    os.remove('./instance/telegram_automation.db')
    print('Removed old database')

# Create app and reinitialize database
app = create_app()
with app.app_context():
    db.create_all()
    print('Created new database with current schema')
    
    # Re-insert critical configs
    from app.models import AppConfig
    AppConfig.set('business_goal', 'adult content sales', 'Business goal')
    AppConfig.set('discovery_topic_context', 'adult content sales', 'Topic context')
    db.session.commit()
    print('Restored AppConfig values')
