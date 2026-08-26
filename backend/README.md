# CrimeLens AI - Backend Service

FastAPI backend service for CrimeLens AI investigator dashboard and evidence processing platform.

## Setup Instructions

### 1. Prerequisites
- Python 3.10+ installed

### 2. Create Virtual Environment
```bash
cd backend
python -m venv venv
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configuration
Copy the example environment file:
```bash
cp .env.example .env
```

### 5. Running the Application
Start the Uvicorn development server:
```bash
uvicorn app.main:app --reload --port 8000
```
- Interactive API Documentation (Swagger UI): `http://127.0.0.1:8000/docs`
- Alternative Documentation (ReDoc): `http://127.0.0.1:8000/redoc`
- Health Check Endpoint: `http://127.0.0.1:8000/api/v1/health`

### 6. Running Tests
```bash
pytest
```
