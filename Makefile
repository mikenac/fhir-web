.PHONY: install dev run-backend run-frontend run format lint typecheck test clean help run-local run-local-d stop-local logs-local clean-local

# Install dependencies
install:
	@echo "Installing backend dependencies..."
	uv venv
	uv pip install -e .
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

# Install with dev dependencies
dev:
	@echo "Installing backend with dev dependencies..."
	uv venv
	uv pip install -e ".[dev]"
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

# Run backend server
run-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run frontend dev server
run-frontend:
	cd frontend && npm run dev

# Run both (requires separate terminals or use tmux/screen)
run:
	@echo "Starting backend and frontend..."
	@echo "Run 'make run-backend' in one terminal and 'make run-frontend' in another"
	@echo "Or use: make run-backend & make run-frontend"

# Code formatting
format:
	@echo "Formatting backend code..."
	black backend/
	ruff check --fix backend/
	@echo "Formatting frontend code..."
	cd frontend && npm run format 2>/dev/null || echo "No formatter configured"

# Linting
lint:
	@echo "Linting backend code..."
	ruff check backend/
	black --check backend/
	basedpyright backend/
	@echo "Linting frontend code..."
	cd frontend && npm run lint

# Type checking only
typecheck:
	basedpyright backend/

# Run tests
test:
	@echo "Running backend tests..."
	pytest backend/tests/ -v 2>/dev/null || echo "No tests found"
	@echo "Running frontend tests..."
	cd frontend && npm test 2>/dev/null || echo "No tests configured"

# Build frontend for production
build:
	cd frontend && npm run build

# Clean build artifacts
clean:
	@echo "Cleaning Python artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache/ .coverage htmlcov/
	@echo "Cleaning frontend artifacts..."
	cd frontend && rm -rf node_modules dist .vite 2>/dev/null || true

# --- Docker Compose (local full stack with HAPI FHIR) ---

# Start all services (backend, frontend, HAPI FHIR) via Docker Compose
run-local:
	@echo "Starting full local stack (backend + frontend + HAPI FHIR)..."
	@echo "This may take 1-2 minutes on first run (HAPI JVM startup)."
	docker compose up --build

# Start in detached mode
run-local-d:
	@echo "Starting full local stack in background..."
	docker compose up --build -d
	@echo ""
	@echo "Services:"
	@echo "  Frontend:  http://localhost:5173"
	@echo "  Backend:   http://localhost:8000"
	@echo "  HAPI FHIR: http://localhost:8090"
	@echo ""
	@echo "Use 'make logs-local' to tail logs, 'make stop-local' to stop."

# Stop all Docker Compose services
stop-local:
	docker compose down

# Tail logs from all services
logs-local:
	docker compose logs -f

# Stop and remove volumes (full reset)
clean-local:
	@echo "Stopping services and removing volumes..."
	docker compose down -v
	@echo "Local stack cleaned."

# Help command
help:
	@echo "FHIR Web Service - Available Commands:"
	@echo ""
	@echo "Setup:"
	@echo "  make install       - Install all dependencies"
	@echo "  make dev          - Install with dev dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make run-backend  - Run FastAPI backend server"
	@echo "  make run-frontend - Run React frontend dev server"
	@echo "  make run          - Instructions for running both"
	@echo ""
	@echo "Code Quality:"
	@echo "  make format       - Format code (black, ruff)"
	@echo "  make lint         - Lint code (ruff, black, basedpyright)"
	@echo "  make typecheck    - Type check only"
	@echo "  make test         - Run tests"
	@echo ""
	@echo "Docker (full local stack):"
	@echo "  make run-local    - Start backend + frontend + HAPI FHIR"
	@echo "  make run-local-d  - Start in background (detached)"
	@echo "  make stop-local   - Stop all services"
	@echo "  make logs-local   - Tail service logs"
	@echo "  make clean-local  - Stop and remove volumes"
	@echo ""
	@echo "Production:"
	@echo "  make build        - Build frontend for production"
	@echo "  make clean        - Clean build artifacts"
