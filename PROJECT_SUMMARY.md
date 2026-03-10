# FHIR Web Project Summary

## Overview

A modern, full-stack web application for interacting with FHIR servers, featuring:
- **Backend**: FastAPI with async patterns, wrapping the FHIR client library from `../fhir/`
- **Frontend**: React with Vite, modern JavaScript (ES6+), and React Query
- **Architecture**: Clean separation of concerns with dependency injection

## Technology Stack

### Backend
- **FastAPI**: Modern async web framework
- **Pydantic**: Data validation and settings management
- **httpx**: Async HTTP client (via FHIR library)
- **uvicorn**: ASGI server
- **Python 3.11+**: Type hints and async/await

### Frontend
- **React 18**: Component-based UI
- **Vite**: Fast build tool and dev server
- **React Router**: Client-side routing
- **React Query (TanStack)**: Data fetching and caching
- **Axios**: HTTP client
- **Modern CSS**: Custom properties and flexbox/grid

## Project Structure

```
fhir_web/
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   │   ├── patients.py         # Patient CRUD endpoints
│   │   │   ├── clinical.py         # Clinical data endpoints
│   │   │   └── operational.py      # Operational endpoints
│   │   ├── models/
│   │   │   └── responses.py        # API response models
│   │   ├── middleware/
│   │   │   └── error_handlers.py   # HTTP error handlers
│   │   ├── config.py               # Pydantic settings
│   │   ├── dependencies.py         # DI setup
│   │   └── main.py                 # FastAPI application
│   └── __init__.py
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.js           # Axios API client
│   │   ├── components/
│   │   │   ├── Home.jsx            # Home page
│   │   │   ├── PatientSearch.jsx   # Patient search
│   │   │   ├── PatientDetail.jsx   # Patient details
│   │   │   ├── CreatePatient.jsx   # Create patient form
│   │   │   └── ClinicalData.jsx    # Clinical data query
│   │   ├── App.jsx                 # Main application
│   │   ├── App.css                 # Styles
│   │   └── main.jsx                # Entry point
│   ├── package.json
│   ├── vite.config.js
│   └── .env                        # Frontend config
│
├── pyproject.toml                  # Python dependencies
├── Makefile                        # Development commands
├── .env                            # Backend config
├── .env.example                    # Config template
├── start.sh                        # Quick start script
├── README.md                       # Full documentation
├── QUICKSTART.md                   # Quick start guide
└── .gitignore
```

## Key Features

### Backend Features

1. **RESTful API**: Following REST principles with proper HTTP methods and status codes
2. **Async Operations**: All endpoints use async/await for optimal performance
3. **Type Safety**: Full Pydantic models for request validation and response serialization
4. **Error Handling**: Global exception handlers for FHIR client errors
5. **CORS Support**: Configured for local development with customizable origins
6. **Dependency Injection**: FastAPI dependencies for clean service management
7. **Auto Documentation**: Swagger UI and ReDoc automatically generated

### Frontend Features

1. **Interactive UI**: Clean, responsive interface for FHIR operations
2. **Real-time Search**: Patient search with instant results
3. **Patient Management**: Create, view, and search patients
4. **Clinical Data View**: Display encounters, orders, medications, referrals
5. **Error Handling**: User-friendly error messages
6. **Loading States**: Visual feedback during API calls
7. **React Query**: Automatic caching and background refetching
8. **Routing**: Multi-page application with React Router

## API Endpoints

### Patient Management
- `POST /api/patients/` - Create new patient
- `GET /api/patients/{patient_id}` - Get patient by ID
- `GET /api/patients/mrn/{mrn}` - Get patient by MRN
- `GET /api/patients/?family_name=X&given_name=Y` - Search patients
- `PUT /api/patients/{patient_id}` - Update patient

### Clinical Data
- `POST /api/clinical/encounters` - Create encounter
- `GET /api/clinical/encounters/{encounter_id}` - Get encounter
- `GET /api/clinical/patients/{patient_id}/encounters` - Get patient encounters
- `POST /api/clinical/orders` - Create order
- `GET /api/clinical/patients/{patient_id}/orders` - Get patient orders
- `POST /api/clinical/medications` - Create medication order
- `GET /api/clinical/patients/{patient_id}/medications` - Get medications
- `POST /api/clinical/referrals` - Create referral
- `GET /api/clinical/patients/{patient_id}/referrals` - Get referrals

### Operational Data
- `POST /api/operational/practitioners` - Create practitioner
- `GET /api/operational/practitioners/{id}` - Get practitioner
- `GET /api/operational/practitioners/npi/{npi}` - Search by NPI
- `POST /api/operational/coverage` - Create coverage
- `GET /api/operational/patients/{id}/coverage` - Get coverage
- `POST /api/operational/schedules` - Create schedule
- `GET /api/operational/practitioners/{id}/schedules` - Get schedules
- `POST /api/operational/slots` - Create appointment slot
- `GET /api/operational/schedules/{id}/slots` - Get available slots

### System
- `GET /` - Root endpoint with health status
- `GET /health` - Health check endpoint

## Design Patterns

### Backend Patterns

1. **Dependency Injection**: FastAPI's DI system for service management
2. **Repository Pattern**: Services from FHIR library handle data access
3. **DTO Pattern**: Pydantic models for data transfer
4. **Error Handling Middleware**: Centralized exception handling
5. **Configuration Management**: Pydantic Settings for env variables

### Frontend Patterns

1. **Component Composition**: Reusable React components
2. **Custom Hooks**: Via React Query for data fetching
3. **Centralized API Client**: Single Axios instance with interceptors
4. **Separation of Concerns**: API logic separated from UI components
5. **Optimistic Updates**: React Query handles caching and updates

## Configuration

### Backend (.env)
```bash
FHIR_BASE_URL=https://hapi.fhir.org/baseR4
FHIR_AUTH_TOKEN=
FHIR_TIMEOUT=30
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
DEBUG=false
```

### Frontend (frontend/.env)
```bash
VITE_API_BASE_URL=http://localhost:8000
```

## Development Workflow

1. **Install**: `make install`
2. **Run Backend**: `make run-backend` (port 8000)
3. **Run Frontend**: `make run-frontend` (port 5173)
4. **Format**: `make format`
5. **Lint**: `make lint`
6. **Test**: `make test`
7. **Clean**: `make clean`

## Async Patterns

The application follows best practices for async programming:

### Backend
- All route handlers are async
- FHIR client uses async httpx
- Proper context manager usage for resource cleanup
- Async dependencies with generators

### Frontend
- React Query for async state management
- Axios for async HTTP requests
- Proper error boundaries
- Loading and error states

## Security Considerations

1. **CORS**: Configured for allowed origins
2. **Input Validation**: Pydantic models validate all inputs
3. **Error Messages**: Sanitized error responses
4. **Environment Variables**: Secrets in .env (not committed)
5. **HTTPS**: Should be used in production
6. **Authentication**: Ready for OAuth2/SMART integration

## Extensibility

### Adding New FHIR Resources

1. **Backend**:
   - Create new router in `backend/app/routers/`
   - Add response models if needed
   - Register router in `main.py`

2. **Frontend**:
   - Add API methods to `frontend/src/api/client.js`
   - Create component in `frontend/src/components/`
   - Add route to `App.jsx`

### Customizing UI

- Modify `frontend/src/App.css` for global styles
- Edit component files for UI changes
- Add new components as needed

## Production Deployment

### Backend
```bash
# Install production dependencies
uv pip install -e .

# Run with production server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend
```bash
# Build for production
cd frontend && npm run build

# Serve with nginx, caddy, or similar
# Files will be in frontend/dist/
```

## Integration with FHIR Client Library

The backend integrates with the FHIR client library from `../fhir/`:

- **Dynamic Import**: Python path manipulation in dependencies.py
- **Service Layer**: Direct use of PatientService, ClinicalService, OperationalService
- **Models**: Reuse of Pydantic input models from FHIR library
- **Client Management**: Context manager pattern for proper cleanup

## Future Enhancements

Possible additions:
- [ ] Authentication/Authorization (OAuth2/SMART)
- [ ] WebSocket support for real-time updates
- [ ] Batch operations
- [ ] Advanced search filters
- [ ] Data export functionality
- [ ] Audit logging
- [ ] Rate limiting
- [ ] Caching layer (Redis)
- [ ] Unit and integration tests
- [ ] Docker deployment
- [ ] CI/CD pipeline

## Performance

- **Backend**: Async operations prevent blocking
- **Frontend**: React Query provides caching and background updates
- **HTTP/2**: Supported via httpx
- **Connection Pooling**: Built into httpx client
- **Bundle Size**: Optimized with Vite

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Modern ES6+ features required

## Dependencies

### Backend (Python)
- fastapi >= 0.108.0
- uvicorn >= 0.25.0
- httpx >= 0.26.0
- pydantic >= 2.5.0
- pydantic-settings >= 2.1.0
- fhir.resources >= 7.1.0

### Frontend (JavaScript)
- react 18.3+
- react-router-dom 7.6+
- @tanstack/react-query 6.0+
- axios 1.7+
- vite 6.0+

## Makefile Commands

```bash
make install       # Install all dependencies
make dev           # Install with dev dependencies
make run-backend   # Start FastAPI server
make run-frontend  # Start Vite dev server
make format        # Format code (black, ruff)
make lint          # Lint code (ruff, black, basedpyright)
make typecheck     # Type check Python code
make test          # Run tests
make build         # Build frontend for production
make clean         # Clean build artifacts
make help          # Show all commands
```

## License

MIT

## Created

This project was created following the patterns from the FHIR client library at `../fhir/`, with:
- Modern async FastAPI backend
- React frontend with Vite
- Clean architecture and separation of concerns
- Comprehensive error handling
- Production-ready patterns
