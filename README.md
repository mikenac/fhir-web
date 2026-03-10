# FHIR Web Service

A modern web application for interacting with FHIR servers. Built with FastAPI backend and React frontend.

## Features

- **Patient Management**: Search, create, and view patient records
- **Clinical Data**: Query encounters, orders, medications, and referrals
- **Operational Data**: Manage practitioners, schedules, and coverage
- **Modern UI**: Responsive React interface with real-time queries
- **Type-Safe**: Full type safety with Pydantic and TypeScript support
- **Async**: Built on async/await patterns for optimal performance

## Architecture

```
fhir_web/
├── backend/                 # FastAPI backend
│   └── app/
│       ├── routers/        # API endpoints
│       ├── models/         # Response models
│       ├── middleware/     # Error handlers
│       ├── config.py       # Configuration
│       ├── dependencies.py # DI setup
│       └── main.py         # FastAPI app
├── frontend/               # React frontend
│   └── src/
│       ├── api/           # API client
│       ├── components/    # React components
│       ├── App.jsx        # Main app
│       └── App.css        # Styles
└── pyproject.toml         # Python dependencies
```

## Prerequisites

- Python 3.11+
- Node.js 18+
- uv (Python package installer)
- Access to a FHIR server (uses public HAPI FHIR server by default)

## Installation

### Quick Start

```bash
# Install all dependencies
make install

# Or install with dev dependencies
make dev
```

### Manual Installation

```bash
# Backend
uv venv
uv pip install -e .

# Frontend
cd frontend
npm install
```

## Configuration

1. Copy the example environment files:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

2. Edit `.env` to configure your FHIR server:

```bash
FHIR_BASE_URL=https://hapi.fhir.org/baseR4
FHIR_AUTH_TOKEN=your-token-if-required
```

3. Edit `frontend/.env` if needed:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## Running the Application

### Option 1: Separate Terminals (Recommended)

**Terminal 1 - Backend:**
```bash
make run-backend
```

**Terminal 2 - Frontend:**
```bash
make run-frontend
```

### Option 2: Manual Start

**Backend:**
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm run dev
```

## Accessing the Application

- **Frontend UI**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **Alternative API Docs**: http://localhost:8000/redoc (ReDoc)

## API Endpoints

### Patients
- `POST /api/patients/` - Create patient
- `GET /api/patients/{patient_id}` - Get patient by ID
- `GET /api/patients/mrn/{mrn}` - Get patient by MRN
- `GET /api/patients/` - Search patients
- `PUT /api/patients/{patient_id}` - Update patient

### Clinical
- `POST /api/clinical/encounters` - Create encounter
- `GET /api/clinical/patients/{patient_id}/encounters` - Get patient encounters
- `POST /api/clinical/orders` - Create order
- `GET /api/clinical/patients/{patient_id}/orders` - Get patient orders
- `POST /api/clinical/medications` - Create medication order
- `GET /api/clinical/patients/{patient_id}/medications` - Get patient medications
- `POST /api/clinical/referrals` - Create referral
- `GET /api/clinical/patients/{patient_id}/referrals` - Get patient referrals

### Operational
- `POST /api/operational/practitioners` - Create practitioner
- `GET /api/operational/practitioners/{id}` - Get practitioner
- `GET /api/operational/practitioners/npi/{npi}` - Search by NPI
- `POST /api/operational/coverage` - Create coverage
- `GET /api/operational/patients/{id}/coverage` - Get patient coverage
- `POST /api/operational/schedules` - Create schedule
- `POST /api/operational/slots` - Create appointment slot

## Development

### Code Formatting

```bash
make format
```

### Linting

```bash
make lint
```

### Type Checking

```bash
make typecheck
```

### Running Tests

```bash
make test
```

## Building for Production

```bash
# Build frontend
make build

# Frontend will be built to frontend/dist/
```

To serve in production:

```bash
# Backend with production ASGI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Serve frontend build with nginx or similar
```

## Project Structure

### Backend

The backend follows a clean architecture pattern:

- **Routers**: Handle HTTP requests and responses
- **Dependencies**: Provide service instances via dependency injection
- **Services**: Business logic (from FHIR client library)
- **Models**: Pydantic models for API responses
- **Middleware**: Error handling and request processing
- **Config**: Environment-based configuration

### Frontend

The frontend uses modern React patterns:

- **React Router**: Client-side routing
- **React Query**: Data fetching and caching
- **Axios**: HTTP client
- **Functional Components**: With hooks
- **CSS**: Modern CSS with custom properties

## Extending the Application

### Adding New FHIR Resources

1. **Backend**: Add new router in `backend/app/routers/`
2. **Frontend**: Add API methods in `frontend/src/api/client.js`
3. **Frontend**: Create components in `frontend/src/components/`
4. **Register**: Add router to `main.py` and route to `App.jsx`

### Customizing the UI

- Edit `frontend/src/App.css` for styling
- Modify components in `frontend/src/components/`
- Update API client in `frontend/src/api/client.js`

## Troubleshooting

### Backend won't start

- Check that the FHIR library is accessible at `../fhir/`
- Verify environment variables in `.env`
- Ensure port 8000 is not in use

### Frontend can't connect to backend

- Verify backend is running on port 8000
- Check `VITE_API_BASE_URL` in `frontend/.env`
- Check browser console for CORS errors

### FHIR server connection issues

- Test connectivity: `curl https://hapi.fhir.org/baseR4/metadata`
- Verify `FHIR_BASE_URL` in `.env`
- Check if authentication token is required

## Clean Up

```bash
make clean
```

## License

MIT

## Contributing

Contributions welcome! Please follow the existing code style and run linting before submitting PRs.
