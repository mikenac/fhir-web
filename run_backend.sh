#!/bin/bash
# Script to run the backend server

# Activate virtual environment
source .venv/bin/activate

# Run uvicorn
cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
