import requests, time
from urllib.parse import quote

# ----------------- CONFIG -----------------
ABOT_URL = "http://10.176.27.73/abotrest"
LOGIN_URL = f"{ABOT_URL}/abot/api/v5/login"
CONFIG_URL = f"{ABOT_URL}/abot/api/v5/update_config_properties"
EXECUTE_URL = f"{ABOT_URL}/abot/api/v5/feature_files/execute"
STATUS_URL = f"{ABOT_URL}/abot/api/v5/execution_status"
ARTIFACT_URL = f"{ABOT_URL}/abot/api/v5/latest_artifact_name"
DETAIL_STATUS_URL = f"{ABOT_URL}/abot/api/v5/detail_execution_status"

USERNAME = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"
FEATURE_TAG = "5gs-initial-registration-with-integrity-and-ciphering-sdcore-0.1.2"

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
    requests.post(EXECUTE_URL, headers=headers, json=payload).raise_for_status()
    print("▶️ Test started.")

def poll_both_statuses():
    print("⏳ Polling execution status...")

    while True:
        # --- 1️⃣ High-level execution_status (summary like ABot UI) ---
        res = requests.get(STATUS_URL, headers=headers)
        res.raise_for_status()
        exec_data = res.json().get("executing", {})
        exec_list = exec_data.get("executing", [])
        execution_status = exec_data.get("execution_status", [])

        if execution_status:
            passed = sum(1 for step in execution_status if step.get("status") == 1)
            failed = sum(1 for step in execution_status if step.get("status") != 1)
            print(f"\n📊 High-Level Summary (execution_status): Passed={passed}, Failed={failed}")
            for step in execution_status:
                status = "PASS" if step.get("status") == 1 else "FAIL"
                print(f"Step: {step.get('name')} → {status}")

        # --- 2️⃣ Detailed per-step execution ---
        res_detail = requests.get(DETAIL_STATUS_URL, headers=headers)
        res_detail.raise_for_status()
        detail_data = res_detail.json().get("executing", {})

        total_passed = 0
        total_failed = 0

        print("\n📋 Detailed Execution Status (per-step):")
        for feature, steps in detail_data.items():
        print(f"\nFeature: {feature}")
        for step in steps:
            if isinstance(step, dict):
                name = step.get("name") or step.get("keyword") or "Unknown Step"
                keyword = step.get("keyword") or ""
                status = step.get("status", "unknown")
                duration = step.get("duration", "N/A")
                timestamp = step.get("timestamp", "N/A")
    
                # Normalize status
                if isinstance(status, int):
                    status_str = "passed" if status == 1 else "failed"
                else:
                    status_str = str(status).lower()
            else:
                # Step is string
                name = str(step)
                keyword = ""
                status_str = "unknown"
                duration = "N/A"
                timestamp = "N/A"
    
            print(f"{keyword} {name} → {status_str.upper()} (Duration: {duration}s, Timestamp: {timestamp})")
    
            if status_str == "passed":
                total_passed += 1
            elif status_str == "failed":
                total_failed += 1


        print(f"\n🎯 Total Detailed Passed: {total_passed}, Total Failed: {total_failed}")

        # Stop polling if main execution finished
        if exec_list and not exec_list[0].get("is_executing", True):
            print("\n✅ Execution completed.")
            break
        else:
            print("🟡 Still running... waiting 10s")
            time.sleep(10)



def download_and_print_log(folder):
    log_url = f"{ABOT_URL}/abot/api/v5/artifacts/logs"
    safe_folder = quote(folder, safe='')
    params = {"foldername": safe_folder}
    print("📥 Downloading ABot execution log...")
    res = requests.get(log_url, headers=headers, params=params)
    if res.status_code == 404:
        print(f"⚠️ Log not found for folder: {folder}")
        return
    res.raise_for_status()
    log_text = res.text
    print("📜 ABot Execution Log:\n")
    print(log_text)
    with open("abot_log.log", "w") as f:
        f.write(log_text)

def get_latest_artifact():
    res = requests.get(ARTIFACT_URL, headers=headers)
    res.raise_for_status()
    data = res.json()["data"]
    latest_artifact_name = data["latest_artifact_timestamp"]
    print(f"📁 Latest artifact name: {latest_artifact_name}")
    return latest_artifact_name

# ----------------- MAIN -----------------
if __name__ == "__main__":
    login()
    update_config()
    execute_feature()
    poll_both_statuses()
    folder = get_latest_artifact()
    download_and_print_log(folder)
