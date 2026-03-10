# Quick Start Guide

Get up and running with FHIR Web in 5 minutes!

## Prerequisites

- Python 3.11+ with `uv` installed
- Node.js 18+
- Access to `../fhir/` FHIR client library

## 1. Install Dependencies

```bash
make install
```

Or manually:

```bash
# Backend
uv venv
uv pip install -e .

# Frontend
cd frontend && npm install
```

## 2. Start the Application

### Option A: Use the start script (easiest)

```bash
./start.sh
```

This will start both backend and frontend servers automatically.

### Option B: Use make commands (recommended for development)

**Terminal 1 - Backend:**
```bash
make run-backend
```

**Terminal 2 - Frontend:**
```bash
make run-frontend
```

### Option C: Manual start

**Terminal 1:**
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2:**
```bash
cd frontend
npm run dev
```

## 3. Access the Application

- **Web UI**: http://localhost:5173
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## 4. Try It Out

1. Open http://localhost:5173 in your browser
2. Click "Search Patients" to search the HAPI FHIR test server
3. Try searching for patients with last name "Smith"
4. Click on a patient to view their clinical data
5. Create a new patient using the "Create Patient" form

## Configuration

The default configuration uses the public HAPI FHIR test server:
- `FHIR_BASE_URL=https://hapi.fhir.org/baseR4`

To use a different FHIR server, edit `.env`:

```bash
FHIR_BASE_URL=http://your-fhir-server.com/fhir
FHIR_AUTH_TOKEN=your-token-if-needed
```

## Project Structure

```
fhir_web/
├── backend/               # FastAPI backend
│   └── app/
│       ├── routers/      # API endpoints
│       │   ├── patients.py
│       │   ├── clinical.py
│       │   └── operational.py
│       ├── config.py     # Settings
│       └── main.py       # FastAPI app
├── frontend/             # React frontend
│   └── src/
│       ├── api/         # API client
│       ├── components/  # React components
│       └── App.jsx      # Main app
├── Makefile             # Development commands
├── .env                 # Backend config
└── frontend/.env        # Frontend config
```

## Available Commands

```bash
make install       # Install dependencies
make run-backend   # Run backend server
make run-frontend  # Run frontend server
make format        # Format code
make lint          # Lint code
make test          # Run tests
make clean         # Clean artifacts
make help          # Show all commands
```

## API Endpoints

### Patients
- `POST /api/patients/` - Create patient
- `GET /api/patients/{id}` - Get patient
- `GET /api/patients/` - Search patients
- `GET /api/patients/mrn/{mrn}` - Get by MRN

### Clinical Data
- `GET /api/clinical/patients/{id}/encounters` - Get encounters
- `GET /api/clinical/patients/{id}/orders` - Get orders
- `GET /api/clinical/patients/{id}/medications` - Get medications
- `GET /api/clinical/patients/{id}/referrals` - Get referrals

### Operational
- `GET /api/operational/practitioners/{id}` - Get practitioner
- `GET /api/operational/practitioners/npi/{npi}` - Search by NPI
- `GET /api/operational/patients/{id}/coverage` - Get coverage

Full API documentation available at http://localhost:8000/docs

## Troubleshooting

### Backend won't start
- Verify the FHIR client library exists at `../fhir/`
- Check Python path in `backend/app/dependencies.py`
- Run `make install` to ensure dependencies are installed

### Frontend can't connect to backend
- Ensure backend is running on port 8000
- Check `VITE_API_BASE_URL` in `frontend/.env`
- Look for CORS errors in browser console

### FHIR server errors
- Test connectivity: `curl https://hapi.fhir.org/baseR4/metadata`
- Check `FHIR_BASE_URL` in `.env`
- Some operations may not be supported by test servers

## Next Steps

1. Explore the API documentation at http://localhost:8000/docs
2. Customize the UI in `frontend/src/components/`
3. Add new FHIR resources by creating new routers
4. Configure authentication if your FHIR server requires it
5. Read the full README.md for detailed documentation

## Support

For issues or questions:
- Check the README.md for detailed documentation
- Review the API docs at http://localhost:8000/docs
- Examine the FHIR client library at `../fhir/`
