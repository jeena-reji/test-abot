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
    print("✅ Login successful.\n")


def update_config():
    print("=== Configuration Phase ===")
    payload1 = {"update": {"ABOT.SUTVARS.ORAN": "", "ABOT.SUTVARS": "file:IOSMCN/sut-vars/default5G.properties"}}
    params1 = {"filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABotConfig.properties"}
    requests.post(CONFIG_URL, headers=headers, json=payload1, params=params1, timeout=30).raise_for_status()
    print("✔ Updated sut-vars → ABotConfig.properties")

    payload2 = {"update": {"ABOT.TESTBED": "file:IOSMCN/testbeds/testbed-5G-IOSMCN.properties", "LOAD_SWITCH": "off"}}
    params2 = {"filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABot_System_Configs/ABotConfig_Primary_Configuration.properties"}
    requests.post(CONFIG_URL, headers=headers, json=payload2, params=params2, timeout=30).raise_for_status()
    print("✔ Updated testbed → ABot_Primary_Configuration.properties\n")
    time.sleep(2)


def execute_feature():
    print(f"🚀 Executing feature tag: {FEATURE_TAG}")
    payload = {"params": FEATURE_TAG}
    res = requests.post(EXECUTE_URL, headers=headers, json=payload)
    res.raise_for_status()
    exec_info = res.json().get("data", {})
    execution_id = exec_info.get("executionId") or exec_info.get("timestamp") or FEATURE_TAG
    print(f"▶️ Test started. Execution ID = {execution_id}\n")
    return execution_id


def poll_current_status(exec_id):
    print("⏳ Polling execution status...\n")
    while True:
        try:
            # Fetch high-level execution status
            res = requests.get(STATUS_URL, headers=headers, params={"execution": exec_id}, timeout=30)
            res.raise_for_status()
            json_data = res.json()

            # ABot may return different structures
            data = json_data.get("executing") or json_data.get("execution_status") or []

            # If data is a dict, wrap it in a list
            if isinstance(data, dict):
                data = [data]
            # If data is a string, just print and skip parsing
            if isinstance(data, str):
                print(f"🟡 Execution status: {data}")
                time.sleep(10)
                continue

            # Now safe to iterate
            passed = sum(1 for step in data if isinstance(step, dict) and step.get("status") == 1)
            failed = sum(1 for step in data if isinstance(step, dict) and step.get("status") != 1)
            print(f"🟡 Running... Passed={passed}, Failed={failed}")

            # Stop if nothing is running
            if not data:
                break

            time.sleep(10)

        except requests.exceptions.RequestException as e:
            print(f"⚠️ Polling error: {e}, retrying in 10s")
            time.sleep(10)

    print("\n✅ Execution completed.")



    # --- High-Level Summary ---
    res = requests.get(STATUS_URL, headers=headers, params={"execution": exec_id})
    res.raise_for_status()
    exec_data = res.json().get("executing", {})
    execution_status = exec_data.get("execution_status", [])

    passed = sum(1 for step in execution_status if step.get("status") == 1)
    failed = sum(1 for step in execution_status if step.get("status") != 1)
    print(f"📊 High-Level Summary: Passed={passed}, Failed={failed}\n")
    for step in execution_status:
        status = "PASS" if step.get("status") == 1 else "FAIL"
        print(f"Step: {step.get('name')} → {status}")

    # --- Detailed Execution ---
    res_detail = requests.get(DETAIL_STATUS_URL, headers=headers, params={"execution": exec_id})
    res_detail.raise_for_status()
    detail_data = res_detail.json().get("executing", {})

    if detail_data:
        print("\n📋 Detailed Execution Status:")
        total_passed, total_failed = 0, 0
        for feature, scenarios in detail_data.items():
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

        print(f"\n🎯 Detailed Totals: Passed={total_passed}, Failed={total_failed}\n")
    else:
        print("⚠️ Detailed status not available.\n")


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
    # Clear console at start
    os.system('cls' if os.name == 'nt' else 'clear')

    login()
    update_config()
    exec_id = execute_feature()
    poll_current_status(exec_id)

    folder = get_artifact_by_execution(exec_id)
    if folder:
        download_and_print_log(folder)
