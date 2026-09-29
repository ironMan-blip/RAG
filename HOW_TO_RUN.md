# How to Run the RAG AI Assistant

This document outlines the steps to run both the backend and frontend of the RAG application locally.

## Prerequisites

- **Python 3.9+**
- **Node.js & npm**
- **PostgreSQL** running locally

### 1. Database Setup
Ensure you have a local PostgreSQL instance running. You need to create a database named `rag`.

```bash
# If using the psql CLI:
psql -U postgres -c "CREATE DATABASE rag;"
```
*(The connection string configured in `backend/.env` is `postgresql://postgres:postgres@localhost:5432/rag`. Adjust your local Postgres credentials in `.env` if they are different).*

## 2. Running the Backend

The backend is built with FastAPI and runs on Python.

1. Open a terminal and navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Activate the virtual environment:
   ```bash
   source venv/bin/activate
   ```
3. Install the dependencies (if you haven't already):
   ```bash
   pip install -r requirements.txt
   ```
4. Start the FastAPI server using Uvicorn:
   ```bash
   uvicorn main:app --reload
   ```
   *The backend will typically be accessible at `http://localhost:8000`. You can view the API documentation at `http://localhost:8000/docs`.*

## 3. Running the Frontend

The frontend is a React application powered by Vite.

1. Open a **new terminal window/tab** and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install the Node.js dependencies:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
   *The frontend will usually be accessible at `http://localhost:5173`.*

## 4. Usage
Once both the backend and frontend are running:
1. Open your browser and go to the frontend URL (e.g., `http://localhost:5173`).
2. Upload a file (PDF, text, or image). It will be processed and saved in your PostgreSQL database.
3. Start chatting with your AI assistant using the provided context from your documents!
