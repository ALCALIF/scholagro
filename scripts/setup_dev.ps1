# PowerShell script to quickly setup the dev environment: create DB, run migrations, seed data
# Usage: From repository root in PowerShell
# & .\.venv\Scripts\Activate.ps1
# .\scripts\setup_dev.ps1

Write-Output "Initializing DB and seeding sample data..."
Write-Output "Installing/Updating Python dependencies from requirements.txt..."
pip install --upgrade -r ..\requirements.txt
python -m scripts.init_db
python -m scripts.seed
Write-Output "Done. Run: set FLASK_ENV=development; python run.py"