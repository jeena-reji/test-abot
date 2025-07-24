import requests
import time
import csv
import os

# Configuration
ABOT_URL = "http://10.176.27.73/abotrest/abot/api/v5"
EMAIL = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"

session = requests.Session()
token = None

def log(msg): print(msg)

def login():
    global token
    log("\n🔐 Logging in to ABot...")
    resp = session.post(f"{ABOT_URL}/login", json={"email": EMAIL, "password": PASSWORD})
    if resp.status_code != 200:
        log("❌ Login request failed")
        exit(1)
    data = resp.json().get("data", {})
    token = data.get("token")
    if not token:
        log("❌ No token received!")
        exit(1)
    session.headers.update({"Authorization": f"Bearer {token}"})
    log("✅ Logged in successfully.")

def get_all_features():
    log("\n📋 Fetching all test cases from ABot...")
    resp = session.post(f"{ABOT_URL}/feature_files/list", json={})
    if resp.status_code != 200:
        log(f"❌ Failed to list features: {resp.text}")
        return []
    features = resp.json().get("data", [])
    paths = [f.get("path") for f in features if f.get("path", "").endswith(".feature")]
    log(f"✅ Found {len(paths)} test cases.")
    return paths

def execute_feature(path):
    resp = session.post(f"{ABOT_URL}/feature_files/execute", json={"path": path})
    if resp.status_code != 200:
        log(f"❌ Failed to trigger: {path}")
        return None
    exec_id = resp.json().get("data", {}).get("execution_id")
    log(f"🚀 Triggered: {path} → ID: {exec_id}")
    return exec_id

def poll_status(exec_id, timeout=600):
    log(f"⏳ Waiting for result: {exec_id}")
    start = time.time()
    while time.time() - start < timeout:
        resp = session.get(f"{ABOT_URL}/execution_status")
        if resp.status_code != 200:
            time.sleep(5)
            continue
        for item in resp.json().get("data", []):
            if item.get("execution_id") == exec_id:
                status = item.get("status")
                if status in ["PASS", "FAIL"]:
                    return status
        time.sleep(5)
    return "TIMEOUT"

def run_all():
    login()
    features = get_all_features()
    if not features:
        log("⚠️ No feature files to execute.")
        return

    failed = []
    report_rows = []

    for path in features:
        exec_id = execute_feature(path)
        if not exec_id:
            failed.append((path, "EXEC_FAIL"))
            continue
        status = poll_status(exec_id)
        report_rows.append([path, exec_id, status])
        if status != "PASS":
            failed.append((path, status))
        log(f"🔄 {path} → {status}")

    with open("abot_summary.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Feature File", "Execution ID", "Status"])
        writer.writerows(report_rows)

    if failed:
        log("\n❌ Some tests failed:")
        for f, s in failed:
            log(f"- {f} → {s}")
        exit(1)
    else:
        log("\n✅ All tests passed.")

if __name__ == "__main__":
    run_all()
