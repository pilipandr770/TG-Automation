"""
deploy_hostinger.py
-------------------
Run this on your LOCAL machine (not VPS).
It uses the Hostinger Docker Manager API to:
  1. Find your VPS virtual machine
  2. Find the tg-automation Docker project
  3. Update/rebuild it from the latest docker-compose.yml

Usage:
    python deploy_hostinger.py
"""

import json
import sys
import time
import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────────────────
API_TOKEN    = "QB60lBRk3h8u2N8VFS5BjZFpFVnhfCWhljKOyobPb7478a0f"
BASE_URL     = "https://developers.hostinger.com"
PROJECT_NAME = "tg-automation"   # folder name on VPS: /docker/tg-automation
GITHUB_REPO  = "https://github.com/pilipandr770/TG-Automation.git"
# ─────────────────────────────────────────────────────────────────────────


def api(method: str, path: str, body: dict | None = None):
    url = BASE_URL + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode()), r.status
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        print(f"  ❌ HTTP {e.code}: {body_text}")
        return None, e.code


def step(msg: str):
    print(f"\n{'─'*60}\n{msg}")


# ── 1. List VMs ───────────────────────────────────────────────────────────
step("1. Fetching VPS list...")
vms_data, status = api("GET", "/api/vps/v1/virtual-machines")
if not vms_data:
    print("  ❌ Cannot reach Hostinger API. Check your token or network.")
    sys.exit(1)

vms = vms_data if isinstance(vms_data, list) else vms_data.get("data", [])
if not vms:
    print("  ❌ No VPS found in your account.")
    sys.exit(1)

print("  Found VPS:")
for vm in vms:
    ips = [ip.get("address", "") for ip in vm.get("ip_addresses", [])]
    print(f"    ID={vm['id']}  hostname={vm.get('hostname')}  IPs={ips}")

vm_id = vms[0]["id"]
print(f"  ✅ Using VM id={vm_id}")

# ── 2. List Docker projects ───────────────────────────────────────────────
step("2. Fetching Docker projects on VM...")
projects_data, status = api("GET", f"/api/vps/v1/virtual-machines/{vm_id}/docker")
if projects_data is None:
    print(f"  ⚠️  Cannot list Docker projects (status {status}).")
    projects = []
else:
    projects = projects_data if isinstance(projects_data, list) else projects_data.get("data", [])

if projects:
    print("  Found projects:")
    for p in projects:
        print(f"    name={p.get('name')}  status={p.get('status')}")
else:
    print("  No Docker projects found (or Docker Manager not yet enabled).")

# ── 3. Check if tg-automation exists ─────────────────────────────────────
project_names = [p.get("name", "") for p in projects]
already_exists = PROJECT_NAME in project_names

# ── 4. Deploy / Update ────────────────────────────────────────────────────
if already_exists:
    step(f"3. Project '{PROJECT_NAME}' found — sending UPDATE request...")
    result, st = api(
        "POST",
        f"/api/vps/v1/virtual-machines/{vm_id}/docker/{PROJECT_NAME}/update",
    )
    if result is not None:
        print(f"  ✅ Update triggered (HTTP {st}). Response:")
        print(json.dumps(result, indent=2)[:600])
    else:
        print(f"  ❌ Update request failed (HTTP {st}).")
        print("  Trying alternative: restart...")
        result2, st2 = api(
            "POST",
            f"/api/vps/v1/virtual-machines/{vm_id}/docker/{PROJECT_NAME}/restart",
        )
        if result2 is not None:
            print(f"  ✅ Restart triggered (HTTP {st2}).")
        else:
            print(f"  ❌ Restart also failed (HTTP {st2}).")
            print("""
  ─────────────────────────────────────────────────────
  FALLBACK: Run these commands in Hostinger VPS terminal:

    cd /docker/tg-automation
    git init
    git remote add origin https://github.com/pilipandr770/TG-Automation.git
    git fetch --all
    git checkout -f main
    git rev-parse --short HEAD
    docker compose up -d --build
    docker compose ps
    docker compose logs --tail=200 telethon
  ─────────────────────────────────────────────────────
""")
            sys.exit(1)
else:
    step(f"3. Project '{PROJECT_NAME}' not found — creating via GitHub URL...")
    payload = {
        "project_name": PROJECT_NAME,
        "repository": GITHUB_REPO,
        "branch": "main",
    }
    result, st = api(
        "POST",
        f"/api/vps/v1/virtual-machines/{vm_id}/docker",
        body=payload,
    )
    if result is not None:
        print(f"  ✅ Project created and deploying (HTTP {st}). Response:")
        print(json.dumps(result, indent=2)[:600])
    else:
        print(f"  ❌ Create failed (HTTP {st}).")
        print("""
  ─────────────────────────────────────────────────────
  FALLBACK: Run these commands in Hostinger VPS terminal:

    cp -a /docker/tg-automation /docker/tg-automation.bak.$(date +%F-%H%M)
    rm -rf /docker/tg-automation
    git clone https://github.com/pilipandr770/TG-Automation.git /docker/tg-automation
    cd /docker/tg-automation
    cp /docker/tg-automation.bak.*/.env .env
    docker compose up -d --build
    docker compose ps
    docker compose logs --tail=200 telethon
  ─────────────────────────────────────────────────────
""")
        sys.exit(1)

# ── 5. Poll logs ─────────────────────────────────────────────────────────
step("4. Waiting 60s for containers to come up (postgres healthcheck), then fetching logs...")
for i in range(12):
    print(f"  ... {5*(i+1)}/60s", end="\r")
    time.sleep(5)

logs_data, st = api(
    "GET",
    f"/api/vps/v1/virtual-machines/{vm_id}/docker/{PROJECT_NAME}/logs",
)
if logs_data:
    print("\n  ✅ LIVE LOGS (last portion):\n")
    log_text = logs_data if isinstance(logs_data, str) else json.dumps(logs_data, indent=2)
    print(log_text[-3000:])
else:
    print(f"\n  ⚠️  Could not fetch logs (HTTP {st}). Check Hostinger panel manually.")

# ── 6. Show containers ────────────────────────────────────────────────────
step("5. Checking container status...")
containers_data, st = api(
    "GET",
    f"/api/vps/v1/virtual-machines/{vm_id}/docker/{PROJECT_NAME}/containers",
)
if containers_data:
    containers = containers_data if isinstance(containers_data, list) else containers_data.get("data", [])
    print(f"  {'Container':<35} {'Status':<20} {'Uptime'}")
    print(f"  {'-'*35} {'-'*20} {'-'*15}")
    for c in containers:
        print(f"  {c.get('name','?'):<35} {c.get('status','?'):<20} {c.get('started_at','')}")
else:
    print(f"  ⚠️  Could not fetch container list (HTTP {st}).")

print(f"\n{'='*60}")
print("✅ Deploy script complete. Check logs above for telethon:")
print("   Must see: 'Conversation event handlers registered'")
print("   Must see: 'TELETHON WORKER FULLY STARTED AND RUNNING'")
print(f"{'='*60}\n")
