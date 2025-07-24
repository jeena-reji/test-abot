import requests
import time
import os
import sys

ABOT_BASE_URL = "http://10.176.27.73/abotrest/abot/api/v5"
LOGIN_URL = f"{ABOT_BASE_URL}/login"
FEATURE_LIST_URL = f"{ABOT_BASE_URL}/feature_files"
EXECUTE_URL = f"{ABOT_BASE_URL}/feature_files/execute"
STATUS_URL = f"{ABOT_BASE_URL}/execution_status"
SUMMARY_URL = f"{ABOT_BASE_URL}/artifacts/execFeatureSummary"
LOG_URL = f"{ABOT_BASE_URL}/files"

USERNAME = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"

session = requests.Session()
headers = {}

def login():
    print("🔐 Logging in to ABot...")
    response = session.post(LOGIN_URL, json={"email": USERNAME, "password": PASSWORD})
    response.raise_for_status()
    token = response.json().get("token")
    if not token:
        raise Exception("❌ Login failed, token missing.")
    headers["Authorization"] = f"Bearer {token}"
    print("✅ Logged in successfully.")
    return token

def fetch_features():
    print("📋 Fetching all feature files...")
    response = session.get(FEATURE_LIST_URL, headers=headers)
    response.raise_for_status()
    features = response.json().get("data", [])
    print(f"✅ Found {len(features)} feature files.")
    return features

def execute_feature(feature):
    print(f"🚀 Triggering feature: {feature['path']}")
    payload = {
        "feature_files": [feature["path"]],
        "tags": "",
        "rerun_type": 0
    }
    resp = session.post(EXECUTE_URL, headers=headers, json=payload)
    resp.raise_for_status()
    print("⏳ Waiting for execution to finish...")
    for _ in range(60):
        status = session.get(STATUS_URL, headers=headers).json()
        if status.get("status") == 0:
            print("✅ Execution finished.")
            return
        time.sleep(10)
    raise Exception("❌ Execution timed out.")

def collect_summary_and_logs():
    print("📦 Collecting results...")
    summary_url = f"{SUMMARY_URL}?foldername=latest&page=1&limit=999"
    response = session.get(summary_url, headers=headers)
    if response.ok:
        Path("abot_summary.json").write_text(response.text)
    else:
        print("⚠️ Could not fetch summary.")

    log_path = "artifacts/latest/initial_attach/logs/TestAutomationLog.log"
    log_response = session.get(f"{LOG_URL}?path={log_path}", headers=headers)
    if log_response.ok:
        Path("abot_log.log").write_bytes(log_response.content)
    else:
        print("⚠️ Could not fetch logs.")

def main():
    try:
        login()
        features = fetch_features()
        any_failure = False
        for feature in features:
            execute_feature(feature)
            collect_summary_and_logs()
            if "fail" in feature["name"].lower():
                any_failure = True
        if any_failure:
            print("❌ Some features failed.")
            sys.exit(1)
        else:
            print("✅ All features passed.")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
