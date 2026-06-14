#!/usr/bin/env bash
# =============================================================================
# OWASP ZAP Baseline Scan — Task Manager API
#
# AUTHORIZATION NOTICE: Run this ONLY against your own instance.
#
# Runs the ZAP Docker container in baseline scan mode against the running API.
# Baseline scan: passive analysis + light active scan (safe for dev environments).
#
# Usage:
#   chmod +x pen-tests/zap-scan.sh
#   ./pen-tests/zap-scan.sh                        # scan http://localhost:8000
#   ./pen-tests/zap-scan.sh http://api:8000        # custom target
#   ./pen-tests/zap-scan.sh http://localhost:8000 full  # full active scan
#
# Requirements: Docker Desktop running
# =============================================================================

TARGET="${1:-http://localhost:8000}"
SCAN_MODE="${2:-baseline}"  # baseline | full
REPORT_DIR="$(pwd)/pen-tests/reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$REPORT_DIR"

echo ""
echo "OWASP ZAP — $SCAN_MODE scan"
echo "Target  : $TARGET"
echo "Reports : $REPORT_DIR"
echo "================================================================="

if [ "$SCAN_MODE" = "full" ]; then
  ZAP_SCRIPT="zap-full-scan.py"
  echo "⚠️   Full active scan mode — this sends real attack payloads."
  echo "    Only use against your own isolated environment."
  echo ""
else
  ZAP_SCRIPT="zap-baseline.py"
fi

# Run ZAP via Docker
# -t: target URL
# -r: HTML report filename
# -J: JSON report filename
# -I: do not return failure exit code on alerts (remove to fail on any alert)
# -l: alert level to include in report (PASS, IGNORE, INFO, WARN, FAIL)
docker run --rm \
  --network host \
  -v "$REPORT_DIR":/zap/wrk/:rw \
  -t ghcr.io/zaproxy/zaproxy:stable \
  "$ZAP_SCRIPT" \
  -t "$TARGET" \
  -r "zap-report-${TIMESTAMP}.html" \
  -J "zap-report-${TIMESTAMP}.json" \
  -I \
  -l WARN

EXIT_CODE=$?

echo ""
echo "================================================================="
echo "Scan complete. Reports written to pen-tests/reports/:"
ls -1 "$REPORT_DIR" | grep "$TIMESTAMP"
echo ""
echo "Open the HTML report in a browser:"
echo "  open $REPORT_DIR/zap-report-${TIMESTAMP}.html"
echo ""
echo "Or parse the JSON report:"
echo "  python3 -c \""
echo "  import json; r = json.load(open('$REPORT_DIR/zap-report-${TIMESTAMP}.json'))"
echo "  alerts = r.get('site', [{}])[0].get('alerts', [])"
echo "  for a in alerts: print(a['riskdesc'], a['name'])"
echo "  \""

exit $EXIT_CODE
