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
SUMMARY_URL = f"{ABOT_URL}/abot/api/v5/artifacts/execFeatureSummary"

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

def fetch_summary_report(folder):
    """Fetch execution summary (passed/failed scenarios & steps)"""
    encoded_folder = urllib.parse.quote(folder, safe=":-_.")
    url = f"{ABOT_URL}/abot/api/v5/artifacts/execFeatureSummary?foldername={encoded_folder}&page=1&limit=9999"

    for attempt in range(20):
        try:
            res = requests.get(url, headers=headers, timeout=30)
            if res.status_code == 404:
                print(f"⚠ Summary report not ready yet, attempt {attempt+1}/20")
                time.sleep(10)
                continue
            res.raise_for_status()
            data = res.json()

            if data.get("status") != "ok":
                print("⚠ No summary data found, retrying...")
                time.sleep(10)
                continue

            result = data.get("feature_summary", {}).get("result", {})
            feature_data = result.get("data", {})
            steps = feature_data.get("steps", {}).get("steps", {})
            scenarios = feature_data.get("totalScenarios", {})

            print("\n=== Execution Summary ===")
            print(f"Total Steps - Passed: {steps.get('passed', 0)}, Failed: {steps.get('failed', 0)}, Skipped: {steps.get('skipped', 0)}, Total: {steps.get('total', 0)}")
            print(f"Total Scenarios - Passed: {scenarios.get('totalScenariosPassed', {}).get('totalScenariosPassedNumber', 0)}, Failed: {scenarios.get('totalScenariosFailed', {}).get('totalScenariosFailedNumber', 0)}, Total: {scenarios.get('totalScenariosTotal', {}).get('totalScenariosTotalNumber', 0)}")

            # Optionally print failed scenario names
            print("\nFailed Scenarios:")
            for sc_name, sc_data in feature_data.get("steps", {}).get("scenario", {}).items():
                if sc_data.get("failed", 0) > 0:
                    print(f" - {sc_name}: {sc_data.get('failed')} step(s) failed")
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

        success = fetch_summary_report(artifact_id)
       # ✅ fetch execution summary
        if not success:
            print("⚠ No summary report available.")

    except Exception as e:
        print("❌ ERROR:", str(e))
        sys.exit(1)
    finally:
        print("=== ABot Test Automation Completed ===")

if __name__ == "__main__":
    main()
