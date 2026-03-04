#!/bin/bash

# Start app.py with proper error handling

cd /work/jnh/leadpoet_manage

echo "Starting LeadPoet Manage Dashboard..."
echo "================================="
echo ""

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run with Python unbuffered output to see errors immediately
python -u app.py 2>&1 | tee app.log
