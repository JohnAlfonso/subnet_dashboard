# SN71 Session Manager with Backend API

This project has been refactored to use a **Backend API architecture** where all database operations are handled by a separate backend API server.

## Architecture

```
┌─────────────────┐         HTTP API         ┌─────────────────┐
│   Frontend      │ ──────────────────────> │  Backend API    │
│   (app.py)      │ <────────────────────── │ (backend_api.py)│
│  Port: 8000     │                          │  Port: 9500     │
└─────────────────┘                          └─────────────────┘
                                                       │
                                                       │ Connection Pool
                                                       ▼
                                              ┌─────────────────┐
                                              │   PostgreSQL    │
                                              │   Database      │
                                              └─────────────────┘
```

## Components

### 1. Backend API (`backend_api.py`)
- **Port**: 9500
- **Purpose**: Handles all database operations
- **Connection Pool**: 
  - Min connections: 2
  - Max connections: 10
  - Automatic lifecycle management (startup/shutdown)
- **Features**:
  - Dashboard counts API
  - Session CRUD operations
  - Process CRUD operations
  - Connection pool monitoring
  - CORS enabled for frontend access

### 2. Frontend (`app.py`)
- **Port**: 8000
- **Purpose**: Serves HTML templates and calls backend API
- **Features**:
  - Dashboard with real-time counts and delta tracking
  - Session management (list, create, edit, delete)
  - Process management (list, create, edit, delete)
  - API Credit monitoring (OpenRouter.ai + ScrapingDog)
  - Search and sort functionality
  - Color-coded status indicators

### 3. Database Utilities (`db_utils.py`)
- **Purpose**: Helper functions that call backend API
- All count functions now use HTTP API instead of direct database connections

## Installation

```bash
# Navigate to project directory
cd /work/jnh/leadpoet_manage

# Activate virtual environment (if exists)
source venv/bin/activate

# Install/upgrade dependencies
pip install -r requirements.txt
```

## Running the Application

You need to run **BOTH** servers:

### Option 1: Manual Start

```bash
# Terminal 1: Start Backend API
python backend_api.py

# Terminal 2: Start Frontend
python app.py
```

### Option 2: Using PM2

```bash
# Start backend API
pm2 start backend_api.py --name "backend_api" --interpreter python

# Start frontend
pm2 start app.py --name "dashboard_71" --interpreter python

# View status
pm2 list

# View logs
pm2 logs
```

## API Endpoints

### Dashboard Counts
- `GET /api/counts/raw-company`
- `GET /api/counts/useful-company`
- `GET /api/counts/person-company`
- `GET /api/counts/true-list`
- `GET /api/counts/checked-company`
- `GET /api/counts/generated-leads`
- `GET /api/counts/valued-leads`
- `GET /api/counts/connection-pool`
- `GET /api/counts/max-connections`

### Sessions
- `GET /api/sessions` - List sessions (with search & sort)
- `GET /api/sessions/{id}` - Get session details
- `POST /api/sessions` - Create new session
- `PUT /api/sessions/{id}` - Update session
- `DELETE /api/sessions/{id}` - Delete session

### Processes
- `GET /api/processes` - List processes (with search & sort)
- `GET /api/processes/{id}` - Get process details
- `POST /api/processes` - Create new process
- `PUT /api/processes/{id}` - Update process
- `DELETE /api/processes/{id}` - Delete process

### Health Check
- `GET /health` - Backend API health check

## Features

### Dashboard
- Real-time count display with loading animations
- **Delta tracking**: Compares current counts with previous values
- **Color-coded deltas**:
  - 🟢 Green: Count increased
  - 🔴 Red: Count decreased
  - ⚫ Grey: Count unchanged
- Delta badges show change amount (e.g., +5, -3)
- Database connection monitoring with current/max ratio display

### Session Management
- Full CRUD operations
- Search across all fields
- Sortable columns
- Edit multiple fields per session

### Process Management
- Full CRUD operations
- Search functionality
- Sortable columns
- **Color-coded status badges**:
  - 🟢 Running (green)
  - 🔵 Sleeping (blue)
  - 🔴 Stopped (red)
  - ⚫ Unknown (grey)
- Editable fields: process_name, ip
- Auto-managed fields: id, process_status, monitoring_time

## Configuration

### Backend API URL
- Defined in `db_utils.py` and `app.py`
- Default: `http://localhost:9900`
- Change if running on different host/port

### Database Connection
- Configured in `backend_api.py`
- Database: `mydb`
- User: `myuser`
- Host: `localhost`
- Port: `5432`

### OpenRouter API Key (for API Credit page)
- Set environment variable: `OPENROUTER_API_KEY`
- Get your API key from: https://openrouter.ai/keys

```bash
# Option 1: Set temporarily in terminal
export OPENROUTER_API_KEY="your_api_key_here"

# Option 2: Add to .env file (create from .env.example)
cp .env.example .env
# Edit .env and add your key

# Option 3: Add to your shell profile (~/.bashrc or ~/.zshrc)
echo 'export OPENROUTER_API_KEY="your_api_key_here"' >> ~/.bashrc
source ~/.bashrc
```

### ScrapingDog API Key (for API Credit page)
- Set environment variable: `SCRAPINGDOG_API_KEY`
- Get your API key from: https://scrapingdog.com/dashboard

```bash
# Option 1: Set temporarily in terminal
export SCRAPINGDOG_API_KEY="your_api_key_here"

# Option 2: Add to .env file (create from .env.example)
cp .env.example .env
# Edit .env and add your key

# Option 3: Add to your shell profile (~/.bashrc or ~/.zshrc)
echo 'export SCRAPINGDOG_API_KEY="your_api_key_here"' >> ~/.bashrc
source ~/.bashrc
```

## Troubleshooting

### Backend API not responding
```bash
# Check if backend API is running
curl http://localhost:9900/health

# Should return: {"status": "ok"}
```

### Frontend can't connect to backend
1. Ensure backend API is running on port 9500
2. Check firewall settings
3. Verify `API_BACKEND_URL` in app.py and db_utils.py

### Database connection errors
1. Check PostgreSQL is running
2. Verify database credentials in `backend_api.py`
3. Ensure database exists and tables are created

## Benefits of Backend API Architecture

1. **Separation of Concerns**: Frontend handles UI, backend handles data
2. **Connection Pooling**: Single backend manages database connections efficiently
3. **Scalability**: Frontend and backend can be scaled independently
4. **Reusability**: Backend API can be used by multiple frontends
5. **Maintainability**: Easier to debug and update each component separately
6. **Security**: Database credentials only in backend API

## Files Modified

- ✅ `backend_api.py` (new) - Backend API server
- ✅ `app.py` - Refactored to use API calls
- ✅ `db_utils.py` - Updated to call backend API
- ✅ `requirements.txt` - Added `requests` package
- ✅ All CRUD operations migrated to backend API

## Access URLs

- **Frontend**: http://localhost:8000
- **Backend API**: http://localhost:9900
- **API Docs** (Swagger): http://localhost:9900/docs
- **API Redoc**: http://localhost:9900/redoc
