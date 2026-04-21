@echo off
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo A criar venv com Python oficial...
    python -m venv venv
    echo A instalar dependencias...
    venv\Scripts\python.exe -m pip install --upgrade pip
    venv\Scripts\python.exe -m pip install -r requirements.txt
)

echo A iniciar PortfolioManager em http://localhost:5000
venv\Scripts\python.exe app.py
