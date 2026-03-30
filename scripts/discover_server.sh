#!/bin/bash
# =============================================================================
# NTB Server Discovery Script - READ-ONLY, NON-DESTRUCTIVE
# Project: New_Trade_Bot (Forensic Deployment Rehearsal)
# =============================================================================
# Run from Unraid Web Terminal:
#   bash /mnt/user/herman/Herman/New_Trade_Bot/discover.sh
#   (adjust path if share is on cache or a different mount)
#
# This script ONLY reads system state. It changes NOTHING except writing
# the output report to the same folder.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPORT="$SCRIPT_DIR/server_discovery_report.txt"

{
echo "============================================="
echo " NTB Server Discovery Report"
echo " Generated: $(date)"
echo " Script ran from: $SCRIPT_DIR"
echo "============================================="

echo ""
echo "=== 1. OS IDENTITY ==="
cat /etc/os-release 2>/dev/null || echo "No /etc/os-release"
uname -a 2>/dev/null

echo ""
echo "=== 2. DOCKER VERSION ==="
docker --version 2>&1
docker compose version 2>&1

echo ""
echo "=== 3. RUNNING CONTAINERS ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}\t{{.Image}}" 2>&1

echo ""
echo "=== 4. ALL CONTAINERS (including stopped) ==="
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" 2>&1

echo ""
echo "=== 5. DOCKER NETWORKS ==="
docker network ls 2>&1

echo ""
echo "=== 6. DOCKER VOLUMES ==="
docker volume ls 2>&1

echo ""
echo "=== 7. PORTS IN USE ==="
ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null

echo ""
echo "=== 8. FIND LINUX PATH FOR New_Trade_Bot ==="
find /mnt -maxdepth 6 -type d -name "New_Trade_Bot" 2>/dev/null
echo "---"
find /mnt -maxdepth 6 -type d -name "Herman" 2>/dev/null

echo ""
echo "=== 9. DISK SPACE ==="
df -h 2>/dev/null | grep -E "mnt|cache|user|shm|Filesystem"

echo ""
echo "=== 10. MEMORY ==="
free -h 2>&1

echo ""
echo "=== 11. CPU ==="
lscpu 2>/dev/null | grep -E "Model name|CPU\(s\)|Thread"

echo ""
echo "=== 12. GPU (for Ollama) ==="
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "No NVIDIA GPU or nvidia-smi not found"
ls /dev/dri/ 2>/dev/null || echo "No /dev/dri"

echo ""
echo "=== 13. SHARE MOUNT INFO ==="
mount | grep -i herman 2>/dev/null || echo "No herman mounts found"
echo "---"
ls -la /mnt/user/herman/Herman/ 2>/dev/null || echo "/mnt/user/herman/Herman/ not found"
ls -la /mnt/cache/herman/Herman/ 2>/dev/null || echo "/mnt/cache/herman/Herman/ not found"

echo ""
echo "=== 14. EXISTING DOCKER COMPOSE IN SIBLINGS ==="
find /mnt -maxdepth 7 -name "docker-compose*" -path "*/Herman/*" 2>/dev/null || echo "None found"

echo ""
echo "=== 15. UNRAID DOCKER SETTINGS ==="
cat /boot/config/docker.cfg 2>/dev/null || echo "No docker.cfg found"

echo ""
echo "============================================="
echo " END OF REPORT"
echo "============================================="
} > "$REPORT" 2>&1

echo "Done! Report saved to: $REPORT"
echo "View from Windows: \\\\TOWER\\herman\\Herman\\New_Trade_Bot\\server_discovery_report.txt"
