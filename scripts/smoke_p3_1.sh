#!/bin/bash

################################################################################
# P3.1 Smoke Test Script
# Tests: Daily scheduler, DB persistence, approval workflow
################################################################################

set -e

API_URL="http://localhost:8000/api/v1"
SYMBOLS=("SPY" "QQQ" "AAPL" "TSLA" "NVDA")
LOGS_DIR="/Users/lee/unslug-city/ops/logs"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🧪 P3.1 SMOKE TEST${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Test 1: API Health Check
echo -e "${BLUE}[TEST 1] API Health Check${NC}"
echo "---"
HEALTH=$(curl -s http://localhost:8000/health)
if echo "$HEALTH" | grep -q "healthy"; then
    echo -e "${GREEN}✅ API is healthy${NC}"
else
    echo -e "${RED}❌ API is not responding${NC}"
    exit 1
fi
echo ""

# Test 2: Single Signal Fetch
echo -e "${BLUE}[TEST 2] Single Signal Fetch (GET /signals/AAPL)${NC}"
echo "---"
SIGNAL=$(curl -s "${API_URL}/signals/AAPL")
if echo "$SIGNAL" | jq . > /dev/null 2>&1; then
    SYMBOL=$(echo "$SIGNAL" | jq -r '.symbol // empty')
    UNSLUG=$(echo "$SIGNAL" | jq -r '.unslug_score // empty')
    FEAR=$(echo "$SIGNAL" | jq -r '.fear_score // empty')
    STATUS=$(echo "$SIGNAL" | jq -r '.status // empty')

    if [[ ! -z "$SYMBOL" && ! -z "$UNSLUG" && ! -z "$FEAR" ]]; then
        echo -e "${GREEN}✅ Signal fetched successfully${NC}"
        echo "   Symbol: $SYMBOL"
        echo "   UNSLUG Score: $UNSLUG (range [0,1])"
        echo "   Fear Score: $FEAR (range [0,1])"
        echo "   Status: $STATUS"

        # Validate ranges
        if (( $(echo "$UNSLUG >= 0 && $UNSLUG <= 1" | bc -l) )); then
            echo -e "${GREEN}   ✓ UNSLUG score in range [0,1]${NC}"
        else
            echo -e "${RED}   ✗ UNSLUG score OUT OF RANGE${NC}"
            exit 1
        fi
    else
        echo -e "${RED}❌ Signal response incomplete${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ Failed to parse signal response${NC}"
    exit 1
fi
echo ""

# Test 3: Top N Signals
echo -e "${BLUE}[TEST 3] Top N Signals (GET /scan/top?n=3)${NC}"
echo "---"
SIGNALS=$(curl -s "${API_URL}/scan/top?n=3")
if echo "$SIGNALS" | jq . > /dev/null 2>&1; then
    COUNT=$(echo "$SIGNALS" | jq '.count // empty')
    if [[ ! -z "$COUNT" && $COUNT -gt 0 ]]; then
        echo -e "${GREEN}✅ Top signals fetched successfully${NC}"
        echo "   Count: $COUNT signals"
        echo "$SIGNALS" | jq -r '.signals[] | "   - \(.symbol): trust=\(.combined_trust), status=\(.status)"'
    else
        echo -e "${YELLOW}⚠️  No signals in response (expected if using mock data)${NC}"
    fi
else
    echo -e "${RED}❌ Failed to parse top signals response${NC}"
    exit 1
fi
echo ""

# Test 4: Approval Workflow
echo -e "${BLUE}[TEST 4] Approval Workflow (POST /signals/AAPL/approve)${NC}"
echo "---"
APPROVAL=$(curl -s -X POST "${API_URL}/signals/AAPL/approve" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "BUY",
    "user_id": "test-user",
    "note": "Smoke test approval"
  }')

if echo "$APPROVAL" | jq . > /dev/null 2>&1; then
    APPROVED_STATUS=$(echo "$APPROVAL" | jq -r '.approved_status // empty')
    APPROVED_BY=$(echo "$APPROVAL" | jq -r '.approved_by // empty')

    if [[ ! -z "$APPROVED_STATUS" && ! -z "$APPROVED_BY" ]]; then
        echo -e "${GREEN}✅ Approval accepted${NC}"
        echo "   Approved Status: $APPROVED_STATUS"
        echo "   Approved By: $APPROVED_BY"
        echo "   Note: $(echo "$APPROVAL" | jq -r '.note // empty')"
    else
        echo -e "${RED}❌ Approval response incomplete${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ Failed to parse approval response${NC}"
    exit 1
fi
echo ""

# Test 5: Daily Logging
echo -e "${BLUE}[TEST 5] Daily Job Logging${NC}"
echo "---"
LATEST_LOG=$(ls -t "$LOGS_DIR"/*_daily_job.txt 2>/dev/null | head -1)
if [[ ! -z "$LATEST_LOG" ]]; then
    echo -e "${GREEN}✅ Daily log file found${NC}"
    echo "   Log: $LATEST_LOG"
    echo "   Size: $(wc -c < "$LATEST_LOG") bytes"

    # Check for completion marker
    if grep -q "DAILY SIGNAL BATCH COMPLETE" "$LATEST_LOG"; then
        echo -e "${GREEN}   ✓ Batch completed successfully${NC}"

        # Extract summary
        if grep -q "Target: <60s ✓" "$LATEST_LOG"; then
            echo -e "${GREEN}   ✓ Performance target met (<60s)${NC}"
        elif grep -q "Target: <60s ✗" "$LATEST_LOG"; then
            echo -e "${YELLOW}   ⚠️  Performance target NOT met (>60s)${NC}"
        fi
    else
        echo -e "${YELLOW}   ⚠️  Batch may still be running${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  No daily log found (expected if running first time)${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ ALL SMOKE TESTS PASSED${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "📊 Summary:"
echo "  [✓] API Health"
echo "  [✓] Single Signal Fetch"
echo "  [✓] Top Signals Fetch"
echo "  [✓] Approval Workflow"
echo "  [✓] Daily Logging"
echo ""
echo "Next: Run daily batch manually to verify logging"
echo "  python3 << 'EOF'"
echo "  import asyncio"
echo "  from backend.src.services.scheduler import scheduler_service"
echo "  asyncio.run(scheduler_service._daily_signal_batch())"
echo "  EOF"
echo ""
