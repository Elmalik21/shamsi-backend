# solar_data/management/commands/import_all_data.py
from django.core.management.base import BaseCommand
from django.core.management import call_command
import os

class Command(BaseCommand):
    help = 'Import all data from CSV files in a directory'
    
    def add_arguments(self, parser):
        parser.add_argument('directory', type=str, help='Directory containing CSV files')
    
    def handle(self, *args, **kwargs):
        directory = kwargs['directory']
        
        if not os.path.exists(directory):
            self.stdout.write(self.style.ERROR(f'Directory {directory} does not exist'))
            return
        
        # Look for CSV files
        csv_files = [f for f in os.listdir(directory) if f.lower().endswith('.csv')]
        
        if not csv_files:
            self.stdout.write(self.style.WARNING(f'No CSV files found in {directory}'))
            return
        
        self.stdout.write(f'Found {len(csv_files)} CSV files:')
        for csv_file in csv_files:
            self.stdout.write(f'  - {csv_file}')
        
        # Import each file
        for csv_file in csv_files:
            file_path = os.path.join(directory, csv_file)
            self.stdout.write(self.style.SUCCESS(f'\nImporting {csv_file}...'))
            
            # Use the solar data import command
            try:
                call_command('import_solar_data', file_path)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error importing {csv_file}: {e}'))