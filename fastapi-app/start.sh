#!/bin/bash
playwright install --with-deps chromium
python scheduler.py &
uvicorn main:app --host 0.0.0.0 --port 8000
