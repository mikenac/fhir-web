#!/bin/bash
# Start both backend and frontend servers

echo "Starting FHIR Web Service..."
echo ""

# Check if .env files exist
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

if [ ! -f frontend/.env ]; then
    echo "Creating frontend/.env from frontend/.env.example..."
    cp frontend/.env.example frontend/.env
fi

echo ""
echo "Starting backend server on http://localhost:8000"
echo "Starting frontend server on http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}

trap cleanup EXIT INT TERM

# Start backend
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Start frontend
cd ../frontend && npm run dev &
FRONTEND_PID=$!

# Wait for both processes
wait
