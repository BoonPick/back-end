from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from typing import List, Optional
import os
from datetime import datetime

import mysql.connector

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "163.239.77.78"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "devops"),
    "password": os.getenv("DB_PASSWORD", "Sogangteam2~!"),
    "database": os.getenv("DB_NAME", "boonpick"),
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

app = FastAPI()

@app.get("/")
def read_index():
    return FileResponse("templates/index.html")

class Content(BaseModel):
    id: int
    title: str
    source_name: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None
    raw_content: Optional[str] = None
    refined_content: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@app.get("/contents", response_model=List[Content])
def get_contents():
    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM contents ORDER BY id DESC")
        rows = cursor.fetchall()
        return rows
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

