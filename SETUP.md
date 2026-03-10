# Setup Guide - FHIR Patient Finder

## Prerequisites

- Python 3.11+ with `uv` installed
- Node.js 18+
- FHIR client library at `../fhir/`

## Installation

### 1. Install Python Dependencies

```bash
# Create virtual environment and install backend
uv venv
uv pip install -e .

# Install FHIR library
cd ../fhir && uv pip install -e . && cd ../fhir_web
```

### 2. Install Frontend Dependencies

```bash
cd frontend && npm install && cd ..
```

### 3. Configuration

```bash
# Copy environment files
cp .env.example .env
cp frontend/.env.example frontend/.env
```

The defaults use the public HAPI FHIR test server and should work without modification.

## Running the Application

### Option 1: Use the provided scripts

**Terminal 1 - Backend:**
```bash
./run_backend.sh
```

**Terminal 2 - Frontend:**
```bash
cd frontend && npm run dev
```

### Option 2: Manual commands

**Terminal 1 - Backend:**
```bash
source .venv/bin/activate
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend && npm run dev
```

## Access the Application

- **Web UI**: http://localhost:5173
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Testing the API

```bash
# Health check
curl http://localhost:8000/health

# Search for patients
curl "http://localhost:8000/api/patients/?family_name=Smith&given_name=John"

# Get patient by ID
curl http://localhost:8000/api/patients/3440751
```

## Troubleshooting

###  "No module named 'src.client.fhir_client'"

Make sure you've installed the FHIR library:
```bash
source .venv/bin/activate
cd ../fhir && uv pip install -e . && cd ../fhir_web
```

### Frontend can't connect to backend

1. Check backend is running: `curl http://localhost:8000/health`
2. Verify `VITE_API_BASE_URL` in `frontend/.env` is `http://localhost:8000`
3. Check browser console for CORS errors

### Port already in use

Change the port in the startup command:
```bash
# Backend on different port
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Update frontend/.env
VITE_API_BASE_URL=http://localhost:8001
```

## What's Working

The application is now focused on **finding patients** with three search methods:

1. **Search by Name** - Find patients by first/last name
2. **Search by ID** - Look up patients by FHIR patient ID
3. **Search by MRN** - Find patients by medical record number

Click on any patient result to see their full details.

## Next Steps

The system is currently set up for patient search. Additional features can be added as needed:
- Clinical data queries (encounters, orders, medications)
- Operational data (practitioners, schedules)
- More advanced search filters
- Patient creation/editing
