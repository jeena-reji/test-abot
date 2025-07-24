import requests
import time
import os
import csv

# ABot Configuration
ABOT_URL = "http://10.176.27.73/abotrest/abot/api/v5"
EMAIL = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"
ROOT_PATH = "featureFiles"  # ABot root folder for features
CSV_OUTPUT = "abot_test_summary.csv"

session = requests.Session()
token = None

def log(msg): print(msg)

def login():
    global token
    log("\n🔐 Logging in to ABot...")
    resp = session.post(f"{ABOT_URL}/login", json={"email": EMAIL, "password": PASSWORD})
    log(f"🔎 Status: {resp.status_code}")
    data = resp.json().get("data", {})
    token = data.get("token")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
        log("✅ Logged in successfully.")
    else:
        log("❌ Login failed.")
        exit(1)

def list_folder(path):
    try:
        log(f"📂 Listing: {path}")
        resp = session.get(f"{ABOT_URL}/files", params={"path": path, "include_file": "true"})
        log(f"🔎 Status: {resp.status_code}")
        if resp.status_code == 200:
            return resp.json().get("data", [])
        else:
            log(f"⚠️ Failed to list {path} → {resp.text}")
            return []
    except Exception as e:
        log(f"⚠️ Exception while listing {path}: {e}")
        return []

def find_feature_files(path):
    all_features = []
    stack = [path]
    while stack:
        current = stack.pop()
        items = list_folder(current)
        for item in items:
            full_path = os.path.join(current, item["name"]).replace("\\", "/")
            if item.get("is_file") and full_path.endswith(".feature"):
                all_features.append(full_path)
            elif not item.get("is_file"):
                stack.append(full_path)
    return all_features

def execute_feature(file_path):
    log(f"\n🚀 Triggering execution: {file_path}")
    resp = session.post(f"{ABOT_URL}/feature_files/execute", json={"path": file_path})
    if resp.status_code == 200:
        exec_id = resp.json().get("data", {}).get("execution_id", "")
        log(f"🆔 Execution ID: {exec_id}")
        return exec_id
    else:
        log(f"❌ Failed to execute {file_path} → {resp.text}")
        return None

def wait_for_completion(exec_id, timeout=600):
    log(f"⏳ Waiting for execution {exec_id} to complete...")
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(5)
        resp = session.get(f"{ABOT_URL}/execution_status")
        if resp.status_code != 200:
            continue
        data = resp.json().get("data", [])
        for item in data:
            if item.get("execution_id") == exec_id:
                status = item.get("status")
                log(f"📊 Status for {exec_id}: {status}")
                if status in ["PASS", "FAIL"]:
                    return status
    return "TIMEOUT"

def save_results_csv(results):
    with open(CSV_OUTPUT, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Feature File", "Execution ID", "Status"])
        for row in results:
            writer.writerow(row)
    log(f"\n📄 Saved summary to: {CSV_OUTPUT}")

def main():
    login()
    log(f"\n📁 Discovering all .feature files under `{ROOT_PATH}` recursively...")
    features = find_feature_files(ROOT_PATH)

    if not features:
        log("⚠️ No feature files found.")
        return

    log(f"\n✅ Found {len(features)} feature files.")

    results = []
    failed = []

    for feature in features:
        exec_id = execute_feature(feature)
        if not exec_id:
            results.append([feature, "N/A", "EXECUTION_FAILED"])
            failed.append(feature)
            continue
        status = wait_for_completion(exec_id)
        results.append([feature, exec_id, status])
        if status != "PASS":
            failed.append(feature)

    save_results_csv(results)

    if failed:
        log("\n❌ Some test cases failed:")
        for f in failed:
            log(f"- {f}")
        exit(1)
    else:
        log("\n✅ All feature files passed.")

if __name__ == "__main__":
    main()
