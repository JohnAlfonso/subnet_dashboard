from fastapi import FastAPI, HTTPException, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError, ConfigDict
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from typing import Optional, List, Dict, Any
import uvicorn
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SN71 Backend API")

# Add CORS middleware to allow frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = await request.body()
    logger.error(f"Validation error on {request.method} {request.url}: {exc.errors()}")
    logger.error(f"Request body: {body.decode('utf-8') if body else 'empty'}")
    logger.error(f"Request headers: {dict(request.headers)}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": body.decode('utf-8') if body else 'empty'}
    )

# Database connection pool
DB_POOL: ConnectionPool = None

@app.on_event("startup")
async def startup_event():
    global DB_POOL
    DB_POOL = ConnectionPool(
        conninfo="dbname=mydb user=myuser password=strongpassword host=localhost port=5432",
        min_size=2,
        max_size=5,
        kwargs={"row_factory": dict_row},
        open=True
    )


def ensure_session_pay_date_column():
    """Ensure sn71_session has pay_date column for session management."""
    with DB_POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE sn71_session
                ADD COLUMN IF NOT EXISTS pay_date TIMESTAMP NULL
            """)
            conn.commit()


def ensure_openrouter_keys_table():
    """Ensure OpenRouter key storage table exists for multi-key management."""
    with DB_POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sn71_openrouter_key (
                    id BIGSERIAL PRIMARY KEY,
                    email TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    label TEXT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.commit()


@app.on_event("startup")
async def startup_tasks():
    try:
        # ensure_session_pay_date_column()
        logger.info("Ensured sn71_session.pay_date column exists")
        # ensure_openrouter_keys_table()
        logger.info("Ensured sn71_openrouter_key table exists")
    except Exception as e:
        logger.error(f"Error running startup database bootstrap tasks: {e}")
        raise
    logger.info("Database connection pool initialized")

@app.on_event("shutdown")
async def shutdown_event():
    global DB_POOL
    if DB_POOL:
        DB_POOL.close()
        logger.info("Database connection pool closed")

# ==================== Dashboard Counts API ====================

@app.get("/api/counts/raw-company")
async def get_raw_company_count():
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT count(id) as count
                    FROM sn71_company
                    WHERE
                        m_description IS NULL
                        AND company_check IS NULL
                        AND contact_info IS NULL
                        AND flag3 IS NULL
                """)
                result = cur.fetchone()
                return {"count": result['count'] if result else 0}
    except Exception as e:
        logger.error(f"Error getting raw company count: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/counts/scored-company")
async def get_scored_company_count():
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT count(id) as count
                    FROM sn71_company
                    WHERE
                        m_description IS NULL
                        AND company_check IS NULL
                        AND contact_info IS NULL
                        AND flag3 IS NULL
                        AND resp_score > 18
                """)
                result = cur.fetchone()
                return {"count": result['count'] if result else 0}
    except Exception as e:
        logger.error(f"Error getting scored company count: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/counts/useful-company")
async def get_useful_company_count():
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(id) as count
                    FROM sn71_company
                    WHERE
                        m_description IS NULL
                        AND company_check IS NULL
                        AND contact_info IS NOT NULL
                        AND contact_info <> '{}'::jsonb
                        AND country = 'US'
                        AND resp_score is not null AND resp_score > 0
                        AND flag2 IS NULL
                        AND (contact_info->>'employeesCount')::int <= 5000

                """)
                result = cur.fetchone()
                return {"count": result['count'] if result else 0}
    except Exception as e:
        logger.error(f"Error getting useful company count: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/counts/person-company")
async def get_person_company_count():
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT count(p.id) as count
                    FROM sn71_person p
                    INNER JOIN sn71_company c ON p.c_website = c.website
                    WHERE p.email IS NULL
                        AND p.seen IS NULL
                        AND c.company_check = 1
                """)
                result = cur.fetchone()
                return {"count": result['count'] if result else 0}
    except Exception as e:
        logger.error(f"Error getting person company count: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/counts/true-list")
async def get_true_list_count():
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                # cur.execute("""
                #     SELECT count(id) as count
                #     FROM sn71_person
                #     WHERE email IS NOT NULL
                #         AND email_check = 1
                #         AND seen = 1
                # """)
                cur.execute("""
                    SELECT count(p.id) as count
                    FROM sn71_person p
                    INNER JOIN sn71_company c ON p.c_website = c.website
                    WHERE p.email IS NOT NULL
                        AND p.contactout_info IS NOT NULL
                        AND p.email_check = 1
                        AND p.email_duplicate_check IS NOT TRUE
                        AND p.lead_check IS NULL
                        AND p.processing = 0
                        AND c.company_check = 1
                """)
                result = cur.fetchone()
                return {"count": result['count'] if result else 0}
    except Exception as e:
        logger.error(f"Error getting true list count: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/counts/checked-company")
async def get_checked_company_count():
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                # cur.execute("""
                #     SELECT count(*) as count FROM(SELECT count(c.id)
                #     FROM sn71_person p
                #     INNER JOIN sn71_company c
                #         ON p.c_website = c.website
                #     WHERE
                #         p.contactout_info IS NOT NULL
                #         AND p.email_check = 1
                #         AND p.email_duplicate_check IS NOT TRUE
                #         AND p.lead_check IS NULL
                #         AND p.processing = 0
                #         AND c.company_check = 1
                #     GROUP BY c.id) AS subquery
                # """)
                cur.execute("""
                    SELECT count(id) as count
                    FROM sn71_company
                    WHERE
                        (contact_info ->> 'employeesCount')::int < 1000
                        and (contact_info ->> 'employeesCount')::int > 0
                        and flag1 IS NULL
                        and company_check = 1
                        and country = 'US'
                """)
                result = cur.fetchone()
                return {"count": result['count'] if result else 0}
    except Exception as e:
        logger.error(f"Error getting checked company count: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/counts/checked-company-detail")
async def get_checked_company_detail():
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COALESCE(source, '(Unknown)') AS source,
                        COUNT(source) AS count
                    FROM sn71_company
                    WHERE
                        (contact_info ->> 'employeesCount')::int < 1000
                        AND (contact_info ->> 'employeesCount')::int > 0
                        AND flag1 IS NULL
                        AND company_check = 1
                        AND country = 'US'
                    GROUP BY COALESCE(source, '(Unknown)')
                    ORDER BY count DESC, source ASC
                """)
                details = cur.fetchall()
                total = sum(row["count"] for row in details)
                return {"details": details, "total": total}
    except Exception as e:
        logger.error(f"Error getting checked company detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/counts/generated-leads")
async def get_generated_leads_count():
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT count(id) as count
                    FROM sn71_person
                    WHERE email IS NOT NULL
                        AND email_check = 1
                        AND seen = 302
                """)
                result = cur.fetchone()
                return {"count": result['count'] if result else 0}
    except Exception as e:
        logger.error(f"Error getting generated leads count: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/counts/valued-leads")
async def get_valued_leads_count():
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT count(id) as count
                    FROM sn71_person
                    WHERE seen = 308
                """)
                result = cur.fetchone()
                return {"count": result['count'] if result else 0}
    except Exception as e:
        logger.error(f"Error getting valued leads count: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/counts/valued-leads-detail")
async def get_valued_leads_detail():
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COALESCE(A.source, '(Unknown)') AS source,
                        COUNT(*) AS count
                    FROM sn71_company A
                    LEFT JOIN sn71_person B ON A.website = B.c_website
                    WHERE B.seen = 308
                    GROUP BY COALESCE(A.source, '(Unknown)')
                    ORDER BY count DESC, source ASC
                """)
                details = cur.fetchall()
                total = sum(row["count"] for row in details)
                return {"details": details, "total": total}
    except Exception as e:
        logger.error(f"Error getting valued leads detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/counts/connection-pool")
async def get_connection_pool_count():
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) as count FROM pg_stat_activity WHERE datname = 'mydb'")
                result = cur.fetchone()
                return {"count": result['count'] if result else 0}
    except Exception as e:
        logger.error(f"Error getting connection pool count: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/counts/max-connections")
async def get_max_connections():
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SHOW max_connections")
                result = cur.fetchone()
                return {"count": int(result['max_connections']) if result else 100}
    except Exception as e:
        logger.error(f"Error getting max connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Session CRUD API ====================

@app.get("/api/sessions")
async def list_sessions(
    search: Optional[str] = None,
    sort_by: str = "id",
    order: str = "asc"
):
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                query = "SELECT * FROM sn71_session"
                params = []
                
                if search:
                    query += """ WHERE 
                        CAST(id AS TEXT) LIKE %s OR
                        proxy_ip LIKE %s OR
                        CAST(proxy_port AS TEXT) LIKE %s OR
                        username LIKE %s OR
                        "XSRF_TOKEN" LIKE %s OR
                        "contactout_seesion" LIKE %s OR
                        CAST(expires AS TEXT) LIKE %s OR
                        proxy_user LIKE %s OR
                        proxy_passwd LIKE %s OR
                        process LIKE %s OR
                        description LIKE %s OR
                        CAST(pay_date AS TEXT) LIKE %s
                    """
                    search_param = f"%{search}%"
                    params = [search_param] * 12
                
                valid_columns = ['id', 'proxy_ip', 'proxy_port', 'username', 'XSRF_TOKEN', 
                                 'contactout_seesion', 'expires', 'pay_date', 'proxy_user',
                                 'proxy_passwd', 'process', 'description']
                if sort_by in valid_columns:
                    if '_' in sort_by or sort_by.isupper():
                        sort_by = f'"{sort_by}"'
                    query += f" ORDER BY {sort_by} {order.upper()}"
                else:
                    query += " ORDER BY id ASC"
                
                cur.execute(query, params)
                records = cur.fetchall()
                return {"records": records}
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{record_id}")
async def get_session(record_id: int):
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sn71_session WHERE id = %s", (record_id,))
                record = cur.fetchone()
                
                if not record:
                    raise HTTPException(status_code=404, detail="Session not found")
                
                return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sessions")
async def create_session(data: Dict[str, Any]):
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sn71_session 
                    (proxy_ip, proxy_port, username, "XSRF_TOKEN", "contactout_seesion", 
                     expires, pay_date, proxy_user, proxy_passwd, process, description)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    data.get('proxy_ip'),
                    data.get('proxy_port'),
                    data.get('username'),
                    data.get('xsrf_token'),
                    data.get('contactout_session'),
                    data.get('expires'),
                    data.get('pay_date') or None,
                    data.get('proxy_user'),
                    data.get('proxy_passwd'),
                    data.get('process'),
                    data.get('description')
                ))
                
                result = cur.fetchone()
                conn.commit()
                return {"id": result['id'], "message": "Session created successfully"}
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/sessions/{record_id}")
async def update_session(record_id: int, data: Dict[str, Any]):
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE sn71_session 
                    SET proxy_ip = %s, proxy_port = %s, username = %s,
                        "XSRF_TOKEN" = %s, "contactout_seesion" = %s, expires = %s, pay_date = %s,
                        proxy_user = %s, proxy_passwd = %s, process = %s, description = %s
                    WHERE id = %s
                """, (
                    data.get('proxy_ip'),
                    data.get('proxy_port'),
                    data.get('username'),
                    data.get('xsrf_token'),
                    data.get('contactout_session'),
                    data.get('expires'),
                    data.get('pay_date'),
                    data.get('proxy_user'),
                    data.get('proxy_passwd'),
                    data.get('process'),
                    data.get('description'),
                    record_id
                ))
                
                conn.commit()
                # logger.info(f"Session updated successfully: {data}")
                return {"message": "Session updated successfully"}
    except Exception as e:
        logger.error(f"Error updating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/sessions/{record_id}")
async def delete_session(record_id: int):
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sn71_session WHERE id = %s", (record_id,))
                conn.commit()
                return {"message": "Session deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Process CRUD API ====================

@app.get("/api/processes")
async def list_processes(
    search: Optional[str] = None,
    sort_by: str = "id",
    order: str = "asc"
):
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                query = "SELECT * FROM sn71_process"
                params = []
                
                if search:
                    query += """ WHERE 
                        CAST(id AS TEXT) LIKE %s OR
                        process_name LIKE %s OR
                        ip LIKE %s OR
                        process_status LIKE %s OR
                        CAST(monitoring_time AS TEXT) LIKE %s
                    """
                    search_param = f"%{search}%"
                    params = [search_param] * 5
                
                valid_columns = ['id', 'process_name', 'ip', 'process_status', 'monitoring_time']
                if sort_by in valid_columns:
                    query += f" ORDER BY {sort_by} {order.upper()}"
                else:
                    query += " ORDER BY id ASC"
                
                cur.execute(query, params)
                records = cur.fetchall()
                return {"records": records}
    except Exception as e:
        logger.error(f"Error listing processes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Process Monitoring API ====================

class ProcessStatusUpdate(BaseModel):
    process_name: str
    status: str
    ip: str
    
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "process_name": "python",
                "status": "running",
                "ip": "192.168.1.1"
            }
        }
    )

@app.get("/api/processes/by-ip/{ip}")
async def get_processes_by_ip(ip: str):
    """Get all process names for a specific IP address"""
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT process_name
                    FROM sn71_process
                    WHERE ip = %s
                """, (ip,))
                rows = cur.fetchall()
                process_names = [row['process_name'] for row in rows]
                return {"process_names": process_names}
    except Exception as e:
        logger.error(f"Error getting processes by IP: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/processes/update-status")
async def update_process_status(data: ProcessStatusUpdate):
    """Update process status by process_name and ip"""
    try:
        logger.info(f"Received update-status request: process_name={data.process_name}, status={data.status}, ip={data.ip}")
        process_name = data.process_name
        status = data.status
        ip = data.ip
        
        # Validate that status is not None or empty
        if not status:
            raise HTTPException(status_code=400, detail="Status cannot be empty")
        
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE sn71_process
                    SET process_status = %s,
                        monitoring_time = NOW()
                    WHERE process_name = %s
                      AND ip = %s
                """, (status, process_name, ip))
                rows_affected = cur.rowcount
                conn.commit()
                if rows_affected == 0:
                    logger.warning(f"No rows updated for process_name={process_name}, ip={ip}")
                logger.info(f"Successfully updated process status: {process_name} -> {status} (rows affected: {rows_affected})")
                return {"message": "Process status updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating process status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/processes/{record_id}")
async def get_process(record_id: int):
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sn71_process WHERE id = %s", (record_id,))
                record = cur.fetchone()
                
                if not record:
                    raise HTTPException(status_code=404, detail="Process not found")
                
                return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting process: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/processes")
async def create_process(data: Dict[str, Any]):
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                # Get the next available id
                cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM sn71_process")
                result = cur.fetchone()
                next_id = result['next_id']
                
                # Insert with the calculated id
                cur.execute("""
                    INSERT INTO sn71_process 
                    (id, process_name, ip, process_status, monitoring_time)
                    VALUES (%s, %s, %s, %s, NOW())
                    RETURNING id
                """, (next_id, data.get('process_name'), data.get('ip'), 'unknown'))
                
                result = cur.fetchone()
                conn.commit()
                return {"id": result['id'], "message": "Process created successfully"}
    except Exception as e:
        logger.error(f"Error creating process: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/processes/{record_id}")
async def update_process(record_id: int, data: Dict[str, Any]):
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE sn71_process 
                    SET process_name = %s, ip = %s
                    WHERE id = %s
                """, (data.get('process_name'), data.get('ip'), record_id))
                
                conn.commit()
                return {"message": "Process updated successfully"}
    except Exception as e:
        logger.error(f"Error updating process: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/processes/{record_id}")
async def delete_process(record_id: int):
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sn71_process WHERE id = %s", (record_id,))
                conn.commit()
                return {"message": "Process deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting process: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# ==================== OpenRouter API Credits ====================

def mask_api_key(api_key: str) -> str:
    """Mask an API key for safe UI/API display."""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}{'*' * max(len(api_key) - 8, 4)}{api_key[-4:]}"


def normalize_openrouter_credits_payload(payload: Dict[str, Any]) -> Dict[str, float]:
    credits = payload.get("data", {}) if isinstance(payload, dict) else {}
    total_credits = float(credits.get("total_credits", 0) or 0)
    total_usage = float(credits.get("total_usage", 0) or 0)
    remaining = total_credits - total_usage
    return {
        "total_credits": total_credits,
        "total_usage": total_usage,
        "remaining": remaining
    }


@app.get("/api/openrouter/keys")
async def list_openrouter_keys():
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, email, api_key, label, is_active, created_at, updated_at
                    FROM sn71_openrouter_key
                    ORDER BY id DESC
                """)
                rows = cur.fetchall()

        records = []
        for row in rows:
            records.append({
                "id": row["id"],
                "email": row["email"],
                "label": row["label"],
                "is_active": bool(row["is_active"]),
                "api_key_masked": mask_api_key(row["api_key"]),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
            })

        return {"records": records}
    except Exception as e:
        logger.error(f"Error listing OpenRouter keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/openrouter/keys")
async def create_openrouter_key(data: Dict[str, Any] = Body(...)):
    email = (data.get("email") or "").strip()
    api_key = (data.get("api_key") or "").strip()
    label = (data.get("label") or "").strip() or None
    is_active = bool(data.get("is_active", True))

    if not email:
        raise HTTPException(status_code=400, detail="email is required")
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key is required")

    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sn71_openrouter_key (email, api_key, label, is_active)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, email, api_key, label, is_active, created_at, updated_at
                """, (email, api_key, label, is_active))
                row = cur.fetchone()
                conn.commit()

        return {
            "message": "OpenRouter key created successfully",
            "record": {
                "id": row["id"],
                "email": row["email"],
                "label": row["label"],
                "is_active": bool(row["is_active"]),
                "api_key_masked": mask_api_key(row["api_key"]),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
            }
        }
    except Exception as e:
        logger.error(f"Error creating OpenRouter key: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/openrouter/keys/credits")
async def get_openrouter_keys_credits():
    """Get credit information for each active OpenRouter key."""
    try:
        import requests as req

        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, email, api_key, label, is_active, created_at, updated_at
                    FROM sn71_openrouter_key
                    ORDER BY id DESC
                """)
                rows = cur.fetchall()

        records = []
        for row in rows:
            record = {
                "id": row["id"],
                "email": row["email"],
                "label": row["label"],
                "is_active": bool(row["is_active"]),
                "api_key_masked": mask_api_key(row["api_key"]),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                "total_credits": 0.0,
                "total_usage": 0.0,
                "remaining": 0.0,
                "status": "skipped" if not row["is_active"] else "ok",
                "error": None
            }

            if row["is_active"]:
                try:
                    response = req.get(
                        "https://openrouter.ai/api/v1/credits",
                        headers={"Authorization": f"Bearer {row['api_key']}"},
                        timeout=10
                    )
                    response.raise_for_status()
                    credits_data = normalize_openrouter_credits_payload(response.json())
                    record.update(credits_data)
                except req.exceptions.RequestException as ex:
                    record["status"] = "error"
                    record["error"] = str(ex)
                except Exception as ex:
                    record["status"] = "error"
                    record["error"] = str(ex)

            records.append(record)

        return {"records": records}
    except Exception as e:
        logger.error(f"Error getting OpenRouter key credits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/openrouter/keys/{record_id}")
async def update_openrouter_key(record_id: int, data: Dict[str, Any] = Body(...)):
    email = (data.get("email") or "").strip()
    label = (data.get("label") or "").strip() or None
    api_key_raw = data.get("api_key")
    api_key = api_key_raw.strip() if isinstance(api_key_raw, str) else None
    is_active = bool(data.get("is_active", True))

    if not email:
        raise HTTPException(status_code=400, detail="email is required")

    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                if api_key:
                    cur.execute("""
                        UPDATE sn71_openrouter_key
                        SET email = %s,
                            label = %s,
                            api_key = %s,
                            is_active = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        RETURNING id, email, api_key, label, is_active, created_at, updated_at
                    """, (email, label, api_key, is_active, record_id))
                else:
                    cur.execute("""
                        UPDATE sn71_openrouter_key
                        SET email = %s,
                            label = %s,
                            is_active = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        RETURNING id, email, api_key, label, is_active, created_at, updated_at
                    """, (email, label, is_active, record_id))

                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="OpenRouter key not found")
                conn.commit()

        return {
            "message": "OpenRouter key updated successfully",
            "record": {
                "id": row["id"],
                "email": row["email"],
                "label": row["label"],
                "is_active": bool(row["is_active"]),
                "api_key_masked": mask_api_key(row["api_key"]),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating OpenRouter key {record_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/openrouter/keys/{record_id}")
async def delete_openrouter_key(record_id: int):
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM sn71_openrouter_key
                    WHERE id = %s
                    RETURNING id
                """, (record_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="OpenRouter key not found")
                conn.commit()
        return {"message": "OpenRouter key deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting OpenRouter key {record_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/openrouter/credits")
async def get_openrouter_credits():
    """Get OpenRouter.ai API credits information"""
    try:
        import requests as req
        
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY environment variable not set")
        
        url = "https://openrouter.ai/api/v1/credits"
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        
        response = req.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        credits = data.get("data", {})
        total_credits = credits.get("total_credits", 0)
        total_usage = credits.get("total_usage", 0)
        remaining = total_credits - total_usage
        
        return {
            "total_credits": total_credits,
            "total_usage": total_usage,
            "remaining": remaining
        }
    except req.exceptions.RequestException as e:
        logger.error(f"Error fetching OpenRouter credits: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch credits: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting OpenRouter credits: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ScrapingDog API Credits ====================

@app.get("/api/scrapingdog/credits")
async def get_scrapingdog_credits():
    """Get ScrapingDog API credits information"""
    try:
        import requests as req
        
        api_key = os.getenv("SCRAPINGDOG_API_KEY", "")
        if not api_key:
            raise HTTPException(status_code=500, detail="SCRAPINGDOG_API_KEY environment variable not set")
        
        url = f"https://api.scrapingdog.com/account?api_key={api_key}"
        
        response = req.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Extract key information
        request_limit = data.get("requestLimit", 0)
        request_used = data.get("requestUsed", 0)
        remaining = request_limit - request_used
        
        return {
            "request_limit": request_limit,
            "request_used": request_used,
            "remaining": remaining,
            "raw_data": data  # Include full data for reference
        }
    except req.exceptions.RequestException as e:
        logger.error(f"Error fetching ScrapingDog credits: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch credits: {str(e)}")
    except Exception as e:
        logger.error(f"Error getting ScrapingDog credits: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== SN71 Submissions API ====================

@app.get("/api/submissions")
async def get_submissions():
    """Get all submission data from sn71_submission table"""
    try:
        with DB_POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT hotkey, submissions, max_submissions, rejections, 
                           max_rejections, reset_at
                    FROM sn71_submission
                """)
                rows = cur.fetchall()
                
                # Convert to dictionary keyed by hotkey for easy lookup
                submissions_dict = {}
                for row in rows:
                    submissions_dict[row['hotkey']] = {
                        'submissions': row['submissions'],
                        'max_submissions': row['max_submissions'],
                        'rejections': row['rejections'],
                        'max_rejections': row['max_rejections'],
                        'reset_at': row['reset_at'].isoformat() if row['reset_at'] else None
                    }
                
                return {"submissions": submissions_dict}
    except Exception as e:
        logger.error(f"Error getting submissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9900)
