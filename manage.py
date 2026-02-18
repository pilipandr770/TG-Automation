"""
Database management and admin user creation script.

Usage:
    python manage.py create-admin <username> <email> <password>
    python manage.py create-admin-interactive
    python manage.py init-db
"""
import os
import sys
import click
from dotenv import load_dotenv

load_dotenv()

from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash


@click.group()
def cli():
    """Management commands for Telegram Automation."""
    pass


@cli.command('init-db')
def init_database():
    """Initialize the database (create tables)."""
    app = create_app()
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✓ Database initialized")


@cli.command('create-admin')
@click.argument('username')
@click.argument('email')
@click.argument('password')
def create_admin(username, email, password):
    """Create an admin user with provided credentials."""
    app = create_app()
    with app.app_context():
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            click.secho(f'✗ User "{username}" already exists', fg='red')
            return
        
        # Create new admin user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=True
        )
        
        try:
            db.session.add(user)
            db.session.commit()
            click.secho(f'✓ Admin user "{username}" created successfully', fg='green')
            print(f'  Email: {email}')
            print(f'  Username: {username}')
        except Exception as e:
            db.session.rollback()
            click.secho(f'✗ Error creating user: {e}', fg='red')


@cli.command('create-admin-interactive')
def create_admin_interactive():
    """Create an admin user interactively (prompt for input)."""
    username = click.prompt('Username')
    email = click.prompt('Email')
    password = click.prompt('Password', hide_input=True, confirmation_prompt=True)
    
    app = create_app()
    with app.app_context():
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            click.secho(f'✗ User "{username}" already exists', fg='red')
            return
        
        # Create new admin user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=True
        )
        
        try:
            db.session.add(user)
            db.session.commit()
            click.secho(f'✓ Admin user "{username}" created successfully', fg='green')
        except Exception as e:
            db.session.rollback()
            click.secho(f'✗ Error creating user: {e}', fg='red')


@cli.command('list-users')
def list_users():
    """List all users in the database."""
    app = create_app()
    with app.app_context():
        users = User.query.all()
        if not users:
            click.secho('No users found', fg='yellow')
            return
        
        click.echo(f'\nUsers ({len(users)} total):')
        click.echo('-' * 60)
        for user in users:
            admin_badge = ' [ADMIN]' if user.is_admin else ''
            click.echo(f'  {user.username:<20} {user.email:<30}{admin_badge}')


if __name__ == '__main__':
    cli()
