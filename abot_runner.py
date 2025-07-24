import requests
import time
import os
from urllib.parse import quote

# ABot configuration
ABOT_HOST = "http://10.176.27.73/abotrest"
LOGIN_URL = f"{ABOT_HOST}/abot/api/v5/login"
FEATURE_PATH_API = f"{ABOT_HOST}/abot/api/v5/feature_files_path"
FILES_API = f"{ABOT_HOST}/abot/api/v5/files"
EXECUTE_FEATURE_API = f"{ABOT_HOST}/abot/api/v5/feature_files/execute"
EXECUTION_STATUS_API = f"{ABOT_HOST}/abot/api/v5/execution_status"
EXEC_SUMMARY_API = f"{ABOT_HOST}/abot/api/v5/artifacts/execFeatureSummary"

# Credentials
USERNAME = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"

session = requests.Session()
headers = {"Content-Type": "application/json"}


def login():
    print("🔐 Logging in to ABot...")
    response = session.post(LOGIN_URL, json={"email": USERNAME, "password": PASSWORD})
    print(f"🔎 Status: {response.status_code}")
    print(f"📨 Response: {response.text}")
    response.raise_for_status()
    json_data = response.json()
    token = json_data.get("data", {}).get("token")
    if not token:
        raise Exception("❌ Login failed, token missing in 'data'.")
    headers["Authorization"] = f"Bearer {token}"
    print("✅ Logged in successfully.")


def list_folders(search_path=""):
    response = session.get(FEATURE_PATH_API, headers=headers, params={"search_path": search_path})
    response.raise_for_status()
    data = response.json()
    return data.get("data", [])


def get_feature_files(path):
    response = session.get(FILES_API, headers=headers, params={"path": path})
    response.raise_for_status()
    data = response.json()
    files = data.get("data", [])
    features = []
    for f in files:
        if f.endswith(".feature"):
            features.append(f"{path}/{f}")
    return features


def discover_all_feature_files(root=""):
    print("📁 Discovering all .feature files recursively...")
    feature_files = []
    folders = [root]
    while folders:
        current = folders.pop()
        subfolders = list_folders(current)
        for sub in subfolders:
            folders.append(f"{current}/{sub}" if current else sub)
        feature_files.extend(get_feature_files(current))
    print(f"✅ Found {len(feature_files)} feature files.")
    return feature_files


def execute_feature(feature_path):
    print(f"🚀 Executing: {feature_path}")
    response = session.post(EXECUTE_FEATURE_API, headers=headers, json={"feature_file_tag": feature_path})
    response.raise_for_status()
    print("⏳ Waiting 15s for execution...")
    time.sleep(15)


def get_execution_status():
    response = session.get(EXECUTION_STATUS_API, headers=headers)
    response.raise_for_status()
    return response.json()


def get_summary():
    print("📦 Fetching execution summary...")
    response = session.get(EXEC_SUMMARY_API, headers=headers, params={"foldername": "", "page": 1, "limit": 9999})
    response.raise_for_status()
    return response.json()


def main():
    login()
    feature_files = discover_all_feature_files()
    if not feature_files:
        print("⚠️ No feature files found.")
        return

    failures = []
    for feature in feature_files:
        try:
            execute_feature(feature)
        except Exception as e:
            print(f"❌ Failed to execute {feature}: {e}")
            failures.append(feature)

    print("🧾 Summary:")
    if failures:
        print("❌ Some tests failed:")
        for f in failures:
            print(f"  - {f}")
        exit(1)
    else:
        print("✅ All features passed.")


if __name__ == "__main__":
    main()
