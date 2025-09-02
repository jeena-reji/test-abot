import requests
import time
import sys
import os
import json

# ABot endpoints
ABOT_URL = "http://10.176.27.73/abotrest"
LOGIN_URL = f"{ABOT_URL}/abot/api/v5/login"
CONFIG_URL = f"{ABOT_URL}/abot/api/v5/update_config_properties"
EXECUTE_URL = f"{ABOT_URL}/abot/api/v5/feature_files/execute"
DETAIL_STATUS_URL = f"{ABOT_URL}/abot/api/v5/detail_execution_status"
ARTIFACTS_URL = f"{ABOT_URL}/abot/api/v5/latest_artifact_name"

# Credentials and feature tag
USERNAME = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"
FEATURE_TAG = os.getenv("FEATURE_TAG", "5gs-initial-registration-sdcore-0.0.10")

# Request headers
headers = {"Content-Type": "application/json"}

def login():
    print("Logging in...")
    payload = {"email": USERNAME, "password": PASSWORD, "expires": False}
    res = requests.post(LOGIN_URL, json=payload, timeout=30)
    res.raise_for_status()
    token = res.json().get("data", {}).get("token")
    if not token:
        print(f"❌ Login response missing token: {res.text}")
        sys.exit(1)
    headers["Authorization"] = f"Bearer {token}"
    print("✔ Login successful.")

def update_config():
    print("=== Configuration Phase ===")
    payload1 = {"update": {"ABOT.SUTVARS.ORAN": "", "ABOT.SUTVARS": "file:IOSMCN/sut-vars/default5G.properties"}}
    params1 = {"filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABotConfig.properties"}
    requests.post(CONFIG_URL, headers=headers, json=payload1, params=params1, timeout=30).raise_for_status()
    print("✔ Updated sut-vars → ABotConfig.properties")

    payload2 = {"update": {"ABOT.TESTBED": "file:IOSMCN/testbeds/testbed-5G-IOSMCN.properties", "LOAD_SWITCH": "off"}}
    params2 = {"filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABot_System_Configs/ABotConfig_Primary_Configuration.properties"}
    requests.post(CONFIG_URL, headers=headers, json=payload2, params=params2, timeout=30).raise_for_status()
    print("✔ Updated testbed → ABot_Primary_Configuration.properties")
    time.sleep(5)

def execute_feature():
    print(f"Executing feature tag: {FEATURE_TAG}")
    payload = {"params": FEATURE_TAG}
    res = requests.post(EXECUTE_URL, headers=headers, json=payload, timeout=30)
    res.raise_for_status()
    data = res.json()
    print("Execution response:", json.dumps(data, indent=2))
    print("Response headers:", res.headers)
    return True

def resolve_feature_file_live(feature_tag):
    """Check live execution status for the feature file (from detail_execution_status)."""
    print(f"🔍 Resolving feature file for tag: {feature_tag}")
    for attempt in range(12):  # 2 minutes max
        res = requests.get(DETAIL_STATUS_URL, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()
        executing = data.get("executing", {})
        if executing:
            features = list(executing.keys())
            print(f"👉 Currently executing features: {features}")
            return features[0]
        print(f"⚠ No execution reported yet, retrying... (attempt {attempt+1}/12)")
        time.sleep(10)
    print("❌ Could not resolve feature file during live execution.")
    return None
def resolve_feature_file_final(feature_tag, folder):
    """Resolve the actual feature file(s) from the artifact summary after execution completes."""
    url = f"{ABOT_URL}/abot/api/v5/artifact_summary?artifactId={folder}"
    for attempt in range(12):  # wait up to 2 minutes
        res = requests.get(url, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()
        features = [f["name"] for f in data.get("features", [])]
        if features:
            print(f"📌 Final resolved feature(s) for tag {feature_tag}: {features}")
            return features
        print(f"⚠ No features yet in artifact {folder}, retrying... (attempt {attempt+1}/12)")
        time.sleep(10)
    return []



def poll_status(feature_tag, feature_file):
    print(f"Polling execution status for tag {feature_tag} (file: {feature_file})...")
    while True:
        res = requests.get(DETAIL_STATUS_URL, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()
        executing = data.get("executing", {})

        if feature_file not in executing:
            print(f"⚠ Feature file {feature_file} not found yet.")
            time.sleep(10)
            continue

        scenarios = executing[feature_file]
        print(f"\n📌 Feature: {feature_file}")
        for scenario, steps in scenarios.items():
            print(f"   Scenario: {scenario}")
            for step in steps:
                keyword = step.get("keyword")
                name = step.get("name")
                status = step.get("status", "unknown").upper()
                duration = round(step.get("duration", 0), 3)
                print(f"     [{status}] {keyword} {name} ({duration}s)")

        # Collect statuses
        all_status = [
            step.get("status", "").lower()
            for s in scenarios.values()
            for step in s
        ]
        if all_status and (
            "failed" in all_status
            or all(s in ["passed", "skipped"] for s in all_status)
        ):
            print("\n✔ Execution finished.")
            return True

        time.sleep(30)

def fetch_artifact_id(feature_tag):   # ✅ accept feature_tag
    print("Fetching artifact id for this execution...")
    for attempt in range(30):
        resp = requests.get(ARTIFACTS_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        artifact_folder = data.get("data", {}).get("latest_artifact_timestamp")
        if artifact_folder and feature_tag in artifact_folder:
            print(f"✔ Found artifact folder for {feature_tag}: {artifact_folder}")
            return artifact_folder
        print(f"⚠ Artifact not matching tag yet, retrying... (attempt {attempt+1}/30)")
        time.sleep(10)
    print("❌ Could not fetch artifact folder in time")
    return None

def main():
    print("=== ABot Test Automation Started ===")
    try:
        login()
        update_config()
        execute_feature()

        # ✅ Step 1: Resolve live feature file (fast feedback, may be cached/old)
        live_feature = resolve_feature_file_live(FEATURE_TAG)
        if live_feature:
            print(f"👉 Live detected feature file: {live_feature}")
            poll_status(FEATURE_TAG, live_feature)
        else:
            print("⚠ Could not detect live feature file. Skipping live polling.")

        # ✅ Step 2: After execution finishes, fetch artifact folder
        folder = fetch_artifact_id(FEATURE_TAG)
        if folder:
            print(f"📂 Artifact folder: {folder}")

            # ✅ Step 3: Resolve final feature(s) from artifact_summary (always accurate)
            # final_features = resolve_feature_file_final(FEATURE_TAG, folder)
            # if final_features:
            #     print(f"📌 Final resolved feature(s) for tag {FEATURE_TAG}: {final_features}")
            # else:
            #     print("⚠ Could not resolve final feature mapping from artifact summary.")

    except Exception as e:
        print("❌ ERROR:", str(e))
        sys.exit(1)
    finally:
        print("=== ABot Test Automation Completed ===")



if __name__ == "__main__":
    main()
