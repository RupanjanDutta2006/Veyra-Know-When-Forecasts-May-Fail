#!/bin/bash
# ==============================================================================
# Veyra Phase 5B.2 — AWS EC2 User-Data Bootstrap Launcher (us-east-1)
# Instance: c6i.2xlarge (Ubuntu 22.04 LTS / Amazon Linux 2023)
# ==============================================================================
set -e

echo "=== 1. System Updates & Dependencies ==="
apt-get update -y
apt-get install -y python3-pip python3-dev libeccodes-dev libeccodes-tools curl unzip nginx

echo "=== 2. Python Environment Setup ==="
pip3 install --upgrade pip
pip3 install numpy pandas pyarrow requests eccodes

echo "=== 3. Create Extraction Workspace ==="
mkdir -p /opt/veyra_extraction/cycles
mkdir -p /opt/veyra_extraction/manifests
cd /opt/veyra_extraction

echo "=== 4. Fetch Cloud Worker Script ==="
# Download or write aws_cloud_worker.py
cat << 'EOF' > /opt/veyra_extraction/aws_cloud_worker.py
# (Full content of scripts/aws_cloud_worker.py embedded here)
EOF

echo "=== 5. Execute Extraction ==="
# Add --pilot for pilot test or omit for full 1,040 cycles
python3 /opt/veyra_extraction/aws_cloud_worker.py --pilot

echo "=== 6. Prepare Compact Artifact Server ==="
# Zip compact outputs
cd /opt/veyra_extraction
zip -r /var/www/html/phase5b2_compact_artifacts.zip cycles/ manifests/

echo "=== 7. Auto-Termination (Instance terminates after execution) ==="
# Auto-shutdown immediately after completion
shutdown -h now
