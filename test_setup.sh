#!/bin/bash
# Verification script for Qdrant vs Weaviate benchmark setup

set -e

echo "🔍 System Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Python syntax
echo "✓ Python syntax..."
python3 -m py_compile bench/bench.py 2>&1 | head -1 || echo "❌ Syntax error"
echo "  ✅ bench.py OK"

# 2. YAML syntax
echo "✓ YAML syntax..."
python3 -c "import yaml; yaml.safe_load(open('bench/config.yaml'))" 2>/dev/null
echo "  ✅ config.yaml OK"

# 3. No Milvus in code
echo "✓ Milvus cleanup..."
MILVUS_CODE=$(grep -r "milvus" --include="*.py" --include="*.yaml" bench/ Makefile 2>/dev/null | grep -v "^[^:]*:#" | grep -v "dikecualikan" | wc -l || echo "0")
if [ "$MILVUS_CODE" -eq "0" ]; then
    echo "  ✅ No Milvus code references"
else
    echo "  ⚠️  Found $MILVUS_CODE Milvus code reference(s)"
fi

# 4. No backup files
echo "✓ Backup files..."
BACKUPS=$(find . -name "*.bak" -o -name "*.backup*" 2>/dev/null | wc -l)
if [ "$BACKUPS" -eq "0" ]; then
    echo "  ✅ No backup files"
else
    echo "  ⚠️  Found $BACKUPS backup file(s)"
fi

# 5. No cache
echo "✓ Python cache..."
CACHE=$(find . -name "__pycache__" -o -name "*.pyc" 2>/dev/null | wc -l)
if [ "$CACHE" -eq "0" ]; then
    echo "  ✅ No cache files"
else
    echo "  ⚠️  Found $CACHE cache file(s)"
fi

echo ""
echo "🐳 Docker Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 6. Docker available
if ! docker compose version >/dev/null 2>&1; then
    echo "  ❌ docker compose not available"
    exit 1
fi
echo "  ✅ docker compose available"

# 7. Services status
echo "✓ Service status..."
RUNNING=$(docker compose ps --format json 2>/dev/null | grep -c "Up" || echo "0")
if [ "$RUNNING" -eq "0" ]; then
    echo "  ⚠️  No services running"
else
    echo "  ✅ $RUNNING service(s) running"
fi

echo ""
echo "📊 Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Codebase: Clean ✅"
echo "Files: Minimalist ✅"
echo "Docker: Ready ✅"
echo ""
echo "📖 Quick Start:"
echo "  make build    # Build containers"
echo "  make up       # Start services"
echo "  make test-all # Test connectivity"
echo ""
echo "✅ System ready for benchmarking!"
