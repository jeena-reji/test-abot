import requests
import time
import sys
import json
import os

# ABot endpoints
ABOT_URL = "http://10.176.27.73/abotrest"
LOGIN_URL = f"{ABOT_URL}/abot/api/v5/login"
CONFIG_URL = f"{ABOT_URL}/abot/api/v5/update_config_properties"
EXECUTE_URL = f"{ABOT_URL}/abot/api/v5/feature_files/execute"
STATUS_URL = f"{ABOT_URL}/abot/api/v5/execution_status"
ARTIFACTS_URL = f"{ABOT_URL}/abot/api/v5/latest_artifact_name"
SUMMARY_URL = f"{ABOT_URL}/abot/api/v5/artifacts/execFeatureSummary"

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
    payload1 = {
        "update": {
            "ABOT.SUTVARS.ORAN": "",
            "ABOT.SUTVARS": "file:IOSMCN/sut-vars/default5G.properties"
        }
    }
    params1 = {
        "filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABotConfig.properties"
    }
    requests.post(CONFIG_URL, headers=headers, json=payload1, params=params1, timeout=30).raise_for_status()
    print("✔ Updated sut-vars → ABotConfig.properties")

    payload2 = {
        "update": {
            "ABOT.TESTBED": "file:IOSMCN/testbeds/testbed-5G-IOSMCN.properties",
            "LOAD_SWITCH": "off"
        }
    }
    params2 = {
        "filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABot_System_Configs/ABotConfig_Primary_Configuration.properties"
    }
    requests.post(CONFIG_URL, headers=headers, json=payload2, params=params2, timeout=30).raise_for_status()
    print("✔ Updated testbed → ABot_Primary_Configuration.properties")
    time.sleep(5)


def wait_for_system_ready():
    print("Waiting for system to be ready after config...")
    time.sleep(10)


def execute_feature():
    print(f"Executing feature tag: {FEATURE_TAG}")
    payload = {"params": FEATURE_TAG}
    res = requests.post(EXECUTE_URL, headers=headers, json=payload, timeout=30)
    res.raise_for_status()
    print("✔ Test execution started.")
    try:
        print("Execution response:", json.dumps(res.json(), indent=2))
    except Exception:
        print("Raw execution response:", res.text)


def poll_status():
    print("Polling execution status...")
    while True:
        res = requests.get(STATUS_URL, headers=headers, timeout=30)
        res.raise_for_status()
        exec_info = res.json().get("executing", {})

        executing_list = exec_info.get("executing", [])
        statuses = exec_info.get("execution_status", [])

        # ✅ Only print relevant block for this execution
        print("Filtered execution status:")
        filtered_statuses = []
        for s in statuses:
            # Some steps might have the feature file name including the tag or feature name
            if FEATURE_TAG in s.get("name", "") or s.get("name", "").endswith(".feature") or "execution completed" in s.get("name", ""):
                filtered_statuses.append(s)
        
        print(json.dumps(filtered_statuses, indent=2))
        
        if any(s["name"] == "execution completed" and s["status"] == 1 for s in filtered_statuses):
            print("✔ ABot reports execution completed for current tag.")
            print("Waiting for artifacts to be generated...")
            time.sleep(15)
            return True



def find_artifact_folder(artifacts, feature_tag):
    for folder in artifacts:
        folder_name = ""
        if isinstance(folder, dict):
            folder_name = (
                folder.get("latest_artifact_timestamp")
                or folder.get("label")
                or folder.get("name")
                or ""
            )
        else:
            folder_name = str(folder)

        print(f"Debug: Checking artifact folder '{folder_name}'")

        # ✅ ABot artifact format: <date-time>@<tag>
        if f"@{feature_tag}" in folder_name:
            print(f"✔ Found matching artifact folder: {folder_name}")
            return folder_name

    return None


def fetch_artifacts():
    print("Waiting for artifacts to be generated...")
    for attempt in range(30):
        resp = requests.get(ARTIFACTS_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        print(f"Debug: Artifacts API response keys: {list(data.keys())}")

        artifacts = data.get("data", [])
        print(f"Debug: Found {len(artifacts)} total artifacts in 'data' field")

        folder = find_artifact_folder(artifacts, FEATURE_TAG)
        if folder:
            return folder

        print(f"⚠ No artifact yet for tag {FEATURE_TAG}, retrying... (attempt {attempt+1}/30)")
        time.sleep(10)

    print(f"❌ Could not find matching artifact folder for this tag.")
    return None


def fetch_summary(folder):
    print("Fetching execution summary...")
    resp = requests.get(SUMMARY_URL, headers=headers, params={"artifact_folder": folder}, timeout=30)
    resp.raise_for_status()
    summary = resp.json()
    print("Summary response:", json.dumps(summary, indent=2))
    return summary


def check_result(summary, folder):
    print("=== Result Check ===")
    result = summary.get("feature_summary", {}).get("result", {})
    features = result.get("data", [])

    all_passed = True
    failed_features = []

    for f in features:
        feature_name = f.get("featureName", "UNKNOWN")
        status = f.get("features", {}).get("status", "").lower()
        print(f"Feature {feature_name}: {status.upper()}")

        if status != "passed":
            all_passed = False
            failed_features.append((f))

    # Print detailed summary JSON (for debugging/reference)
    print(json.dumps(result, indent=2))

    # Failure Analysis
    if failed_features:
        print("❌ Some features FAILED ❌")
        print("=== Failure Analysis ===")
        for f in failed_features:
            name = f.get("featureName", "UNKNOWN")
            status = f.get("features", {}).get("status", "unknown")

            steps = f.get("steps", {})
            scenarios = f.get("scenario", {})

            print(f"- Feature: {name} | status={status}")
            print(f"  Steps → passed={steps.get('passed', 0)}, failed={steps.get('failed', 0)}, skipped={steps.get('skipped', 0)}, total={steps.get('total', 0)}")
            print(f"  Scenarios → passed={scenarios.get('passed', 0)}, failed={scenarios.get('failed', 0)}, total={scenarios.get('total', 0)}")

        print(f"📂 Logs for artifact folder {folder} would be downloaded/printed here.")
    else:
        print("✔ All features PASSED ✅")

    return all_passed


def main():
    print("=== ABot Test Automation Started ===")
    if not FEATURE_TAG:
        print("❌ ERROR: FEATURE_TAG environment variable not set")
        sys.exit(1)

    try:
        login()
        update_config()
        execute_feature()
        if not poll_status():
            print("❌ Execution did not complete in time")
            sys.exit(1)

        folder = fetch_artifacts()
        if not folder:
            print("❌ No artifact folder found, cannot proceed with summary.")
            sys.exit(1)

        summary = fetch_summary(folder)
        test_passed = check_result(summary, folder)

        if test_passed:
            print("✔ All features PASSED ✅")
        else:
            print("❌ Some features FAILED ❌")

        sys.exit(0 if test_passed else 1)

    except Exception as e:
        print("❌ ERROR:", str(e))
        sys.exit(1)

    finally:
        print("=== ABot Test Automation Completed ===")


if __name__ == "__main__":
    main()
