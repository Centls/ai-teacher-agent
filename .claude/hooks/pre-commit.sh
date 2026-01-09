#!/bin/bash
# Pre-commit hook: 提交前检查

echo "🔍 Running pre-commit checks..."

# 1. 检查 Python 格式
echo "  ✓ Checking Python code..."
if ! python -m black --check src/ 2>/dev/null; then
    echo "  ⚠️  Python code needs formatting (run: black src/)"
fi

# 2. 检查前端 TypeScript
echo "  ✓ Checking TypeScript..."
cd frontend
if ! npm run typecheck 2>/dev/null; then
    echo "  ⚠️  TypeScript errors found"
    cd ..
    exit 1
fi
cd ..

# 3. 检查环境变量
echo "  ✓ Checking .env configuration..."
if ! grep -q "OPENAI_API_KEY=" .env; then
    echo "  ❌ Missing OPENAI_API_KEY in .env"
    exit 1
fi

echo "✅ Pre-commit checks passed!"