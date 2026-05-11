# solar_data/management/commands/create_admin.py
"""
Creates a superuser/staff admin account if it doesn't already exist.
Reads credentials from env vars:
  ADMIN_USERNAME  (default: admin)
  ADMIN_EMAIL     (default: admin@shamsi.app)
  ADMIN_PASSWORD  (default: ShamsiAdmin2026!)

Run:
  python manage.py create_admin
Or set in railway.json startCommand.
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Create admin superuser from environment variables (idempotent)'

    def handle(self, *args, **options):
        User = get_user_model()

        username = os.environ.get('ADMIN_USERNAME', 'admin')
        email    = os.environ.get('ADMIN_EMAIL',    'admin@shamsi.app')
        password = os.environ.get('ADMIN_PASSWORD', 'ShamsiAdmin2026!')

        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            # Ensure staff/superuser flags are set even if user exists
            updated = False
            if not user.is_staff:
                user.is_staff = True
                updated = True
            if not user.is_superuser:
                user.is_superuser = True
                updated = True
            if updated:
                user.save()
                self.stdout.write(self.style.WARNING(
                    f'User "{username}" already exists — updated to superuser/staff.'
                ))
            else:
                self.stdout.write(f'Admin user "{username}" already exists. Skipping.')
        else:
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(
                f'Superuser created: {username} / {password}'
            ))
