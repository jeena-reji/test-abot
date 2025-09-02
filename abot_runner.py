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
ARTIFACTS_URL = f"{ABOT_URL}/abot/api/v5/latest_artifact_name"
ARTIFACT_SUMMARY_URL = f"{ABOT_URL}/abot/api/v5/artifact_summary"
EXEC_FEATURE_SUMMARY_URL = f"{ABOT_URL}/abot/api/v5/artifacts/execFeatureSummary"


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
    return True

def fetch_artifact_id(tag):
    """Fetch the latest artifact folder corresponding to the executed tag."""
    print("Fetching artifact id for this execution...")
    for attempt in range(30):
        resp = requests.get(ARTIFACTS_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        artifact_folder = data.get("data", {}).get("latest_artifact_timestamp")
        if artifact_folder and tag in artifact_folder:
            print(f"✔ Found artifact folder for {tag}: {artifact_folder}")
            return artifact_folder
        print(f"⚠ Artifact not matching tag yet, retrying... (attempt {attempt+1}/30)")
        time.sleep(10)
    print("❌ Could not fetch artifact folder in time")
    return None

def fetch_detailed_results(folder):
    """Fetch executed feature files and scenario results from artifact execFeatureSummary."""
    url = f"{EXEC_FEATURE_SUMMARY_URL}?artifactId={folder}"
    for attempt in range(20):  # retry up to ~3 minutes
        try:
            res = requests.get(url, headers=headers, timeout=30)
            if res.status_code == 404:
                print(f"⚠ Detailed artifact summary not ready yet, retrying... (attempt {attempt+1}/20)")
                time.sleep(10)
                continue
            res.raise_for_status()
            data = res.json()
            features = data.get("features", [])
            for feature in features:
                feature_name = feature.get("name")
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
            return  # success
        except requests.HTTPError as e:
            print(f"❌ HTTP error: {e}, retrying...")
            time.sleep(10)
    print(f"❌ Could not fetch detailed artifact summary for folder {folder} after multiple attempts")


def main():
    print("=== ABot Test Automation Started ===")
    try:
        login()
        update_config()
        execute_feature()

        artifact_folder = fetch_artifact_id(FEATURE_TAG)
        if not artifact_folder:
            print("❌ Could not retrieve artifact folder, aborting.")
            return

        fetch_detailed_results(artifact_folder)

    except Exception as e:
        print("❌ ERROR:", str(e))
        sys.exit(1)
    finally:
        print("=== ABot Test Automation Completed ===")

if __name__ == "__main__":
    main()
