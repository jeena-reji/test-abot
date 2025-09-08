import requests
import time
import sys
import os
import json
import urllib.parse

# ABot endpoints
ABOT_URL = "http://10.176.27.73/abotrest"
LOGIN_URL = f"{ABOT_URL}/abot/api/v5/login"
CONFIG_URL = f"{ABOT_URL}/abot/api/v5/update_config_properties"
EXECUTE_URL = f"{ABOT_URL}/abot/api/v5/feature_files/execute"
LATEST_ARTIFACT_URL = f"{ABOT_URL}/abot/api/v5/latest_artifact_name"
EXEC_FEATURE_DETAILS_URL = f"{ABOT_URL}/abot/api/v5/artifacts/execFeatureDetails"
EXEC_FAILURE_DETAILS_URL = f"{ABOT_URL}/abot/api/v5/artifacts/execFailureDetails"

# Credentials and feature tag
USERNAME = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"
FEATURE_TAG = os.getenv("FEATURE_TAG", "5gs-initial-registration-with-integrity-and-ciphering-sdcore-0.1.2")

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

def fetch_latest_artifact(tag):
    print(f"Fetching latest artifact for tag: {tag}")
    for _ in range(30):
        res = requests.get(LATEST_ARTIFACT_URL, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()
        artifact_folder = data.get("data", {}).get("latest_artifact_timestamp")

        if artifact_folder:
            print(f"✔ Found artifact folder: {artifact_folder}")
            return artifact_folder

        print("⚠ Artifact not ready yet, retrying...")
        time.sleep(10)
    print("❌ Could not fetch artifact for tag")
    return None

def fetch_failed_steps(folder):
    print("Fetching failed steps...")
    url = f"{EXEC_FAILURE_DETAILS_URL}?artifactId={folder}"
    
    for attempt in range(20):
        try:
            res = requests.get(url, headers=headers, timeout=30)
            res.raise_for_status()
            data = res.json()
            failures = data.get("failed_steps", [])
            if failures:
                print(f"\n❌ Total Failed Steps: {len(failures)}")
                for f in failures:
                    feature = f.get('feature', 'UNKNOWN')
                    scenario = f.get('scenario', 'UNKNOWN')
                    step = f.get('step', 'UNKNOWN')
                    status = f.get('status', 'FAILED')
                    print(f"[{status}] Feature: {feature}, Scenario: {scenario}, Step: {step}")
                return
            else:
                print(f"⚠ Attempt {attempt+1}/20: No failed steps yet, retrying...")
                time.sleep(10)
        except requests.HTTPError as e:
            print(f"❌ HTTP error: {e}, retrying...")
            time.sleep(10)
    print("✔ No failed steps. All scenarios passed!")

def fetch_detailed_report(folder):
    """Fetch detailed per-feature results using execFeatureDetails"""
    encoded_folder = urllib.parse.quote(folder, safe="")
    feature_file = f"{FEATURE_TAG}.feature"
    encoded_feature_file = urllib.parse.quote(feature_file, safe="")
    encoded_feature_id = urllib.parse.quote(FEATURE_TAG, safe="")

    url = f"{EXEC_FEATURE_DETAILS_URL}?foldername={encoded_folder}&featurename={encoded_feature_file}&featureId={encoded_feature_id}"

    for attempt in range(20):
        try:
            res = requests.get(url, headers=headers, timeout=30)
            if res.status_code == 404:
                print(f"⚠ Detailed report not ready yet, attempt {attempt+1}/20")
                time.sleep(10)
                continue
            res.raise_for_status()
            data = res.json()
            features = data.get("features", [])
            if not features:
                print("⚠ No feature data found")
                return False

            for feature in features:
                feature_name = feature.get("name", "UNKNOWN")
                print(f"\n📌 Feature: {feature_name}")
                scenarios = feature.get("scenarios", {})
                for scenario_name, steps in scenarios.items():
                    print(f"   Scenario: {scenario_name}")
                    for step in steps:
                        status = step.get("status", "UNKNOWN").upper()
                        keyword = step.get("keyword", "")
                        name = step.get("name", "")
                        duration = round(step.get("duration", 0), 3)
                        print(f"     [{status}] {keyword} {name} ({duration}s)")
            return True
        except requests.HTTPError as e:
            print(f"❌ HTTP error: {e}, retrying...")
            time.sleep(10)
    return False

def main():
    print("=== ABot Test Automation Started ===")
    try:
        login()
        update_config()
        execute_feature()

        artifact_id = fetch_latest_artifact(FEATURE_TAG)
        if not artifact_id:
            print("❌ Could not retrieve artifact, aborting.")
            return

        fetch_failed_steps(artifact_id)          # ✅ failure reasons
        success = fetch_detailed_report(artifact_id)  # ✅ detailed step-level logs

        if not success:
            print("⚠ No detailed report available.")

    except Exception as e:
        print("❌ ERROR:", str(e))
        sys.exit(1)
    finally:
        print("=== ABot Test Automation Completed ===")

if __name__ == "__main__":
    main()
