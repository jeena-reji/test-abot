import requests
import time
import os

# ABot Configuration
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
    log(f"🔎 Status: {resp.status_code}")
    try:
        data = resp.json().get("data", {})
        token = data.get("token")
        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})
            log(f"🪪 Token set: {session.headers.get('Authorization')}")
            log("✅ Logged in successfully.")
        else:
            log("❌ Login failed, token missing.")
            exit(1)
    except Exception as e:
        log(f"❌ Login failed: {e}")
        exit(1)

def list_folder(path):
    try:
        log(f"\n📂 Listing folder: {path}")
        resp = session.get(f"{ABOT_URL}/files", params={"path": path, "include_file": "true"})
        log(f"🔎 Status: {resp.status_code}")
        if resp.status_code == 200:
            return resp.json().get("data", [])
        else:
            log(f"⚠️ Failed to list {path} → {resp.text}")
            return []
    except Exception as e:
        log(f"⚠️ Error listing {path}: {e}")
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
    resp = session.post(f"{ABOT_URL}/feature_files/execute", json={"path": file_path})
    if resp.status_code == 200:
        exec_id = resp.json().get("data", {}).get("execution_id", "")
        log(f"🚀 Triggered: {file_path} → Execution ID: {exec_id}")
        return exec_id
    else:
        log(f"❌ Failed to execute {file_path} → {resp.text}")
        return None

def wait_for_completion(exec_id, timeout=600):
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
                if status in ["PASS", "FAIL"]:
                    return status
    return "TIMEOUT"

def main():
    login()
    log("📁 Discovering all .feature files recursively...")

    # ✅ Correct root path used: "otherFeatureFile/"
    base_paths = [
        "otherFeatureFile/3GPP-23401-4G",
        "otherFeatureFile/3GPP-23502-5G",
        "otherFeatureFile/3GPP-38401-5G-ORAN",
        "otherFeatureFile/Conformance",
        "otherFeatureFile/IMS",
        "otherFeatureFile/IOS_MCN_5GC_Pre_Release0.1.2",
        "otherFeatureFile/IOS_MCN_5GC_Release0.0.10",
        "otherFeatureFile/IOS_MCN_5GC_UPDATED",
        "otherFeatureFile/Load_for_10_gNB",
        "otherFeatureFile/System_Tests"
    ]

    features = []
    for path in base_paths:
        features += find_feature_files(path)

    if not features:
        log("⚠️ No feature files found.")
        return

    log(f"✅ Found {len(features)} feature files.")

    failed = []
    for feature in features:
        exec_id = execute_feature(feature)
        if not exec_id:
            failed.append(feature)
            continue
        status = wait_for_completion(exec_id)
        log(f"🔄 {feature} → {status}")
        if status != "PASS":
            failed.append(feature)

    if failed:
        log("\n❌ Some feature files failed:")
        for f in failed:
            log(f"- {f}")
        exit(1)
    else:
        log("\n✅ All feature files passed.")

if __name__ == "__main__":
    main()
