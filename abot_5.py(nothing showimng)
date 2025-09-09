import requests, time, os, json
from urllib.parse import quote

# ----------------- CONFIG -----------------
ABOT_URL = "http://10.176.27.73/abotrest"
LOGIN_URL = f"{ABOT_URL}/abot/api/v5/login"
CONFIG_URL = f"{ABOT_URL}/abot/api/v5/update_config_properties"
EXECUTE_URL = f"{ABOT_URL}/abot/api/v5/feature_files/execute"
STATUS_URL = f"{ABOT_URL}/abot/api/v5/execution_status"
DETAIL_STATUS_URL = f"{ABOT_URL}/abot/api/v5/detail_execution_status"
ARTIFACT_BY_EXEC_URL = f"{ABOT_URL}/abot/api/v5/artifacts/by_execution"
LOG_URL = f"{ABOT_URL}/abot/api/v5/artifacts/logs"

USERNAME = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"
FEATURE_TAG = os.getenv("FEATURE_TAG", "5gs-initial-registration-sdcore-0.0.10")

headers = {"Content-Type": "application/json"}


# ----------------- FUNCTIONS -----------------
def login():
    print("🔐 Logging in...")
    payload = {"email": USERNAME, "password": PASSWORD, "expires": False}
    res = requests.post(LOGIN_URL, json=payload)
    res.raise_for_status()
    token = res.json()["data"]["token"]
    headers["Authorization"] = f"Bearer {token}"
    print("✅ Login successful.")


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
    print(f"🚀 Executing feature tag: {FEATURE_TAG}")
    payload = {"params": FEATURE_TAG}
    res = requests.post(EXECUTE_URL, headers=headers, json=payload)
    res.raise_for_status()
    exec_info = res.json().get("data", {})
    execution_id = exec_info.get("executionId") or exec_info.get("timestamp") or FEATURE_TAG
    print(f"▶️ Test started. Execution ID = {execution_id}")
    return execution_id


def poll_both_statuses(exec_id):
    print("⏳ Polling execution status...")
    wait_count = 0
    while True:
        # --- Get current execution only ---
        res = requests.get(STATUS_URL, headers=headers, params={"execution": exec_id})
        res.raise_for_status()
        exec_data = res.json().get("executing", {})


        print("🟡 Current executing keys:", list(exec_data.keys()))
        if not exec_data:
            print("🟡 Waiting for execution data...")
            time.sleep(5)
            continue

        # Filter for the current execution ID
        current_exec = {k: v for k, v in exec_data.items() if k == exec_id}
        if not current_exec:
            if wait_count % 3 == 0:
                print(f"⚠️ Current execution {exec_id} not found yet, waiting...")
            wait_count += 1
            time.sleep(5)
            continue


        execution_status = current_exec[exec_id].get("execution_status", [])
        if execution_status:
            passed = sum(1 for step in execution_status if step.get("status") == 1)
            failed = sum(1 for step in execution_status if step.get("status") != 1)
            print(f"\n📊 High-Level Summary: Passed={passed}, Failed={failed}")
            for step in execution_status:
                status = "PASS" if step.get("status") == 1 else "FAIL"
                print(f"Step: {step.get('name')} → {status}")

        # --- Detailed per-step execution ---
        res_detail = requests.get(DETAIL_STATUS_URL, headers=headers, params={"execution": exec_id})
        res_detail.raise_for_status()
        detail_data = res_detail.json().get("executing", {})
        current_detail = detail_data.get(exec_id, {})

        total_passed, total_failed = 0, 0
        if current_detail:
            print("\n📋 Detailed Execution Status:")
            for feature, scenarios in current_detail.items():
                print(f"\nFeature: {feature}")
                for scenario_name, steps in scenarios.items():
                    print(f"  Scenario: {scenario_name}")
                    for step in steps:
                        keyword = step.get("keyword", "")
                        name = step.get("name", "Unknown Step")
                        status = str(step.get("status", "unknown")).lower()
                        duration = step.get("duration", "N/A")
                        timestamp = step.get("timestamp", "N/A")

                        print(f"    {keyword} {name} → {status.upper()} "
                              f"(Duration: {duration}, Timestamp: {timestamp})")

                        if status == "passed":
                            total_passed += 1
                        elif status == "failed":
                            total_failed += 1

            print(f"\n🎯 Detailed Totals: Passed={total_passed}, Failed={total_failed}")
        else:
            print("⚠️ Detailed status not ready yet.")

        # Stop polling when execution is complete
        if current_exec[exec_id].get("execution_status", []) and all(step.get("status") != 0 for step in execution_status):
            print("\n✅ Execution completed.")
            break
        else:
            print("🟡 Still running... waiting 10s")
            time.sleep(10)


def get_execution_status(exec_id):
    res = requests.get(f"{STATUS_URL}?execution={exec_id}", headers=headers)
    res.raise_for_status()
    return res.json()


def get_detail_execution_status(exec_id):
    res = requests.get(f"{DETAIL_STATUS_URL}?execution={exec_id}", headers=headers)
    res.raise_for_status()
    return res.json()


def get_artifact_by_execution(exec_id):
    res = requests.get(ARTIFACT_BY_EXEC_URL, headers=headers, params={"executionId": exec_id})
    if res.status_code == 404:
        print("⚠️ No artifact found for this execution.")
        return None
    res.raise_for_status()
    data = res.json().get("data", {})
    return data.get("folderName")


def download_and_print_log(folder):
    safe_folder = quote(folder)
    print("📥 Downloading ABot execution log...")
    res = requests.get(LOG_URL, headers=headers, params={"foldername": safe_folder})
    if res.status_code == 404:
        print(f"⚠️ Log not found for folder: {folder}")
        return
    res.raise_for_status()
    log_text = res.text
    print("📜 ABot Execution Log:\n")
    print(log_text)
    with open("abot_log.log", "w") as f:
        f.write(log_text)


# ----------------- MAIN -----------------
if __name__ == "__main__":
    login()
    update_config()
    exec_id = execute_feature()
    poll_both_statuses(exec_id)

    print("\n📊 Fetching High-Level Execution Status...")
    summary = get_execution_status(exec_id)
    print(json.dumps(summary, indent=2))

    print("\n📋 Fetching Detailed Execution Status...")
    details = get_detail_execution_status(exec_id)
    print(json.dumps(details, indent=2))

    folder = get_artifact_by_execution(exec_id)
    if folder:
        download_and_print_log(folder)
