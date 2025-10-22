#!/bin/bash
cd /Users/avimunk/Curserprojects/invoice_handler/backend
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000


# to run it: ./backend/backend_Start.sh