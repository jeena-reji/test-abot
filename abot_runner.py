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
ARTIFACTS_URL = f"{ABOT_URL}/abot/api/v5/artifacts/list"   # 🔹 changed endpoint
SUMMARY_URL = f"{ABOT_URL}/abot/api/v5/detail_execution_status"

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
    data = res.json()
    print("✔ Test execution started.")
    print("Execution response:", json.dumps(data, indent=2))
    # No executionId here, just return tag
    return FEATURE_TAG

def poll_status(tag, timeout=1800):  # 30 min timeout
    print("Polling execution status...")
    start_time = time.time()

    while True:
        if time.time() - start_time > timeout:
            print("❌ ERROR: Polling timed out after 30 minutes.")
            return False

        res = requests.get(STATUS_URL, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()

        exec_info = data.get("execution_status", [])
        detailed = data.get("detailed_status", [])

        # Case 1: execution disappeared
        if not exec_info and not detailed:
            print("✅ No active executions found. Assuming execution completed.")
            return True

        # Case 2: print current execution info
        tag_execs = [s for s in exec_info if tag in s.get("name", "")]
        if tag_execs:
            print("Execution status for current tag:")
            print(json.dumps(tag_execs, indent=2))

        if detailed:
            print(json.dumps(detailed, indent=2))
            if any(s["name"] == "execution completed" and s["status"] == 1 for s in detailed):
                print("✔ ABot reports execution completed.")
                return True

        time.sleep(10)


def fetch_artifact_id(tag):
    print("Fetching artifact id for this execution...")
    for attempt in range(20):
        resp = requests.get(f"{ABOT_URL}/abot/api/v5/artifacts/latest_artifact_name",
                            headers=headers, params={"feature": tag}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        print(f"Debug: /latest_artifact_name response: {json.dumps(data, indent=2)}")

        folder = data.get("data", {}).get("latest_artifact_timestamp")
        if folder:
            print(f"✔ Latest artifact folder: {folder}")
            return folder

        print(f"⚠ No artifact yet, retrying... (attempt {attempt+1}/20)")
        time.sleep(10)

    print("❌ Could not fetch artifact folder in time")
    return None



def fetch_summary(folder):
    print("Fetching execution summary...")
    params = {
        "foldername": folder,
        "page": 1
    }
    resp = requests.get(SUMMARY_URL, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


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
            failed_features.append(f)

    print(json.dumps(result, indent=2))

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
        exec_id = execute_feature()
        if not poll_status(exec_id):
            print("❌ Execution did not complete in time")
            sys.exit(1)

        # ✅ Get artifact folder
        folder = fetch_artifact_id(exec_id)
        if not folder:
            print("❌ No artifact id found, cannot proceed with summary.")
            sys.exit(1)
        print(f"✔ Latest artifact folder: {folder}")

        # ✅ Fetch summary
        print("Fetching execution summary...")
        summary = fetch_summary(folder)
        print(json.dumps(summary, indent=2))

        # ✅ Check pass/fail
        test_passed = check_result(summary, folder)

        sys.exit(0 if test_passed else 1)

    except Exception as e:
        print("❌ ERROR:", str(e))
        sys.exit(1)

    finally:
        print("=== ABot Test Automation Completed ===")


if __name__ == "__main__":
    main()
