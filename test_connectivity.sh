#!/bin/bash

echo "=== Backend & Frontend Connectivity Test ==="
echo ""

echo "1. Testing Backend (Port 8002)..."
if curl -s "http://localhost:8002/threads" > /dev/null 2>&1; then
    echo "✅ Backend is running on port 8002"
    echo "   Response: $(curl -s 'http://localhost:8002/threads' | head -c 100)..."
else
    echo "❌ Backend is NOT running on port 8002"
fi

echo ""
echo "2. Testing Next.js Frontend (Port 3000)..."
if curl -s "http://localhost:3000" > /dev/null 2>&1; then
    echo "✅ Frontend is running on port 3000"
else
    echo "❌ Frontend is NOT running on port 3000"
fi

echo ""
echo "3. Testing Next.js API Route..."
response=$(curl -s -w "\n%{http_code}" "http://localhost:3000/api/agent/threads" 2>&1)
status_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$status_code" = "200" ]; then
    echo "✅ API Route is working (Status: $status_code)"
    echo "   Response: $(echo "$body" | head -c 100)..."
else
    echo "❌ API Route failed (Status: $status_code)"
    echo "   Error: $body"
fi

echo ""
echo "4. Environment Check..."
if [ -f "frontend/.env.local" ]; then
    echo "✅ .env.local exists"
    echo "   Content: $(cat frontend/.env.local)"
else
    echo "❌ .env.local not found"
fi

echo ""
echo "=== Recommendations ==="
if [ "$status_code" != "200" ]; then
    echo "1. Restart the frontend: cd frontend && npm run dev"
    echo "2. Check if BACKEND_URL is set correctly in .env.local"
    echo "3. Verify backend is running: curl http://localhost:8002/threads"
fi