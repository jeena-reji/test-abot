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
LATEST_ARTIFACT_URL = f"{ABOT_URL}/abot/api/v5/latest_artifact_name"

# Credentials and feature tag
USERNAME = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"
FEATURE_TAG = os.getenv("FEATURE_TAG", "5gs-initial-registration-sdcore-0.0.10")

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
    print("Fetching latest artifact folder...")
    for _ in range(30):
        res = requests.get(LATEST_ARTIFACT_URL, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()
        artifact_folder = data.get("data", {}).get("latest_artifact_timestamp")
        if artifact_folder and tag in artifact_folder:
            print(f"✔ Found artifact folder: {artifact_folder}")
            return artifact_folder
        print("⚠ Artifact not ready yet, retrying...")
        time.sleep(10)
    print("❌ Could not fetch artifact folder")
    return None

def read_artifact_summary(artifact_folder):
    """Read summary.json from artifact folder to get pass/fail info"""
    base_path = f"/abot/artifacts/{artifact_folder}"  # change path if needed
    summary_file = os.path.join(base_path, "summary.json")
    features_file = os.path.join(base_path, "features.json")  # if exists

    if not os.path.exists(summary_file):
        print(f"❌ Artifact summary.json not found in {base_path}")
        sys.exit(1)

    with open(summary_file) as f:
        summary = json.load(f)

    print(f"\n📌 Feature Tag: {summary.get('feature_tag', FEATURE_TAG)}")
    print(f"   Total Scenarios: {summary.get('total_scenarios', 0)}")
    print(f"   Passed: {summary.get('passed_scenarios', 0)}")
    print(f"   Failed: {summary.get('failed_scenarios', 0)}")

    # Print each scenario status
    failed_scenarios = []
    for scenario in summary.get("scenarios", []):
        name = scenario.get("name")
        status = scenario.get("status")
        print(f"   - {name}: {status}")
        if status.lower() != "passed":
            failed_scenarios.append(name)

    # Optional: detailed per-feature steps if features.json exists
    if os.path.exists(features_file):
        with open(features_file) as f:
            features = json.load(f)
            for feature in features:
                print(f"\n📌 Feature: {feature.get('name')}")
                for scenario_name, steps in feature.get("scenarios", {}).items():
                    print(f"   Scenario: {scenario_name}")
                    for step in steps:
                        st = step.get("status", "UNKNOWN")
                        kw = step.get("keyword", "")
                        nm = step.get("name", "")
                        dur = round(step.get("duration", 0), 3)
                        print(f"     [{st}] {kw} {nm} ({dur}s)")

    if failed_scenarios:
        print(f"\n❌ Failed Scenarios: {failed_scenarios}")
        sys.exit(1)  # mark GitHub Actions as failed
    else:
        print("\n✔ All scenarios passed!")

def main():
    print("=== ABot Test Automation Started ===")
    try:
        login()
        update_config()
        execute_feature()

        artifact_folder = fetch_latest_artifact(FEATURE_TAG)
        if not artifact_folder:
            print("❌ Could not retrieve artifact folder, aborting.")
            sys.exit(1)

        read_artifact_summary(artifact_folder)

    except Exception as e:
        print("❌ ERROR:", str(e))
        sys.exit(1)
    finally:
        print("=== ABot Test Automation Completed ===")

if __name__ == "__main__":
    main()
