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
    payload = {"params": FEATURE_TAG, "build": "default-build"}  # <--- add build
    res = requests.post(EXECUTE_URL, headers=headers, json=payload)
    res.raise_for_status()

    exec_info = res.json().get("data", {})
    execution_id = exec_info.get("executionId")
    if not execution_id:
        timestamp = exec_info.get("timestamp")
        execution_id = f"{FEATURE_TAG}-{timestamp}" if timestamp else f"{FEATURE_TAG}-{int(time.time())}"

    print(f"▶️ Feature execution requested. Execution ID = {execution_id}\n")
    return execution_id


def find_execution_id(feature_tag, timeout=120):
    print(f"⏳ Waiting for execution of feature '{feature_tag}' to start...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            res = requests.get(STATUS_URL, headers=headers, timeout=10)
            res.raise_for_status()
            all_exec = res.json().get("executing", {})
            if not isinstance(all_exec, dict):
                all_exec = {}

            for exec_id, exec_info in all_exec.items():
                if isinstance(exec_info, dict):
                    feature_files = exec_info.get("feature_files", [])
                    if any(feature_tag in f for f in feature_files):
                        print(f"✅ Execution started: {exec_id}")
                        return exec_id

        except requests.exceptions.RequestException:
            pass

        print("🟡 Execution not started yet... retrying in 5s")
        time.sleep(5)

    print(f"⚠️ Timeout: execution of feature '{feature_tag}' did not start.")
    return None

def poll_current_status(exec_id):
    print("⏳ Polling execution status...\n")
    detail_data = None

    while True:
        try:
            res_detail = requests.get(DETAIL_STATUS_URL, headers=headers, timeout=30)
            all_detail_data = res_detail.json().get("executing", {})
            if not isinstance(all_detail_data, dict):
                all_detail_data = {}

            detail_data = all_detail_data.get(exec_id)
            if not detail_data:
                print("🟡 Execution not started yet for this execution ID...")
                time.sleep(10)
                continue

            running_steps = 0
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

                        if status == "running":
                            running_steps += 1

                        print(f"    {keyword} {name} → {status.upper()} (Duration: {duration}, Timestamp: {timestamp})")

            if running_steps == 0:
                print("\n✅ Execution completed.\n")
                break
            else:
                print(f"\n🟡 Still running... {running_steps} steps in progress. Waiting 10s...\n")
                time.sleep(10)

        except requests.exceptions.RequestException as e:
            print(f"⚠️ Polling error: {e}, retrying in 10s")
            time.sleep(10)

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
    os.system('cls' if os.name == 'nt' else 'clear')

    login()
    update_config()

    # Start execution
    execute_feature()

    # Find the execution ID
    exec_id = find_execution_id(FEATURE_TAG)
    if exec_id:
        poll_current_status(exec_id)
        folder = get_artifact_by_execution(exec_id)
        if folder:
            download_and_print_log(folder)
    else:
        print("❌ Could not find execution for the given feature tag.")
