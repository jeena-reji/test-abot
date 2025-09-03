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

def poll_live_status(timeout_minutes=30):
    print("\n=== Live Execution Log ===")
    scenario_summary = {}
    start_time = time.time()
    finished = False

    while not finished:
        elapsed = (time.time() - start_time) / 60
        if elapsed > timeout_minutes:
            print(f"❌ Timeout reached ({timeout_minutes} minutes). Aborting...")
            break

        res = requests.get(DETAIL_STATUS_URL, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()
        executing = data.get("executing", {})
        feature_file = None

        for f in executing.keys():
            if FEATURE_TAG.replace('-', '_') in f or FEATURE_TAG.lower() in f.lower():
                feature_file = f
                break

        if not feature_file:
            print("⚠ Feature not executing yet, retrying in 10s...")
            time.sleep(10)
            continue

        scenarios = executing[feature_file]
        finished = True  # assume finished unless we find a running step

        for scenario_name, steps in scenarios.items():
            if scenario_name not in scenario_summary:
                scenario_summary[scenario_name] = "PASSED"

            print(f"\n📌 Scenario: {scenario_name}")
            for step in steps:
                status = step.get("status", "UNKNOWN").upper()
                keyword = step.get("keyword", "")
                name = step.get("name", "")
                duration = round(step.get("duration", 0), 3)
                print(f"     [{status}] {keyword} {name} ({duration}s)")

                if status == "FAILED":
                    scenario_summary[scenario_name] = "FAILED"
                elif status not in ["PASSED", "FAILED", "SKIPPED"]:
                    finished = False  # still running

        if not finished:
            time.sleep(10)

    # Final summary
    print("\n=== Execution Summary ===")
    total = len(scenario_summary)
    passed = sum(1 for s in scenario_summary.values() if s == "PASSED")
    failed = sum(1 for s in scenario_summary.values() if s == "FAILED")
    print(f"Total scenarios: {total}, Passed: {passed}, Failed: {failed}")
    for sc, st in scenario_summary.items():
        print(f" - {sc}: {st}")

    if failed > 0:
        sys.exit(1)
    else:
        print("✔ All scenarios passed!")

def main():
    print("=== ABot Test Automation Started ===")
    try:
        login()
        update_config()
        execute_feature()
        poll_live_status()
    except Exception as e:
        print("❌ ERROR:", str(e))
        sys.exit(1)
    finally:
        print("=== ABot Test Automation Completed ===")

if __name__ == "__main__":
    main()
