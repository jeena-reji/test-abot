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
LATEST_ARTIFACT_URL = f"{ABOT_URL}/abot/api/v5/latest_artifact_name"
EXEC_FEATURE_DETAILS = f"{ABOT_URL}/abot/api/v5/artifacts/execFeatureDetails"
EXEC_FAILURE_DETAILS = f"{ABOT_URL}/abot/api/v5/artifacts/execFailureDetails"

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
    payload = {"params": FEATURE_TAG, "build": "default-build"}
    res = requests.post(EXECUTE_URL, headers=headers, json=payload)
    res.raise_for_status()
    print("▶️ Test started.\n")
    time.sleep(2)
    return FEATURE_TAG


def wait_for_new_execution(feature_tag):
    print(f"⏳ Waiting for ABot to switch to execution {feature_tag}...")
    running_shown = False
    while True:
        res = requests.get(STATUS_URL, headers=headers, timeout=30)
        res.raise_for_status()
        data = res.json()
        
        exec_list = data.get("executing", {}).get("executing", [])
        if not exec_list:
            time.sleep(5)
            continue
        
        current_exec = exec_list[0]
        current_name = current_exec.get("name", "").lstrip("@")
        current_id = current_exec.get("id") or current_name
        is_running = current_exec.get("is_executing", False)
        
        if current_name == feature_tag:
            if is_running:
                if not running_shown:
                    print(f"🔄 Execution is running...")
                    running_shown = True
            else:
                print(f"✅ Execution finished: {current_id} (tag={current_name})")
                return current_id
        time.sleep(5)


def poll_current_status(exec_id):
    print("⏳ Polling execution status...\n", flush=True)

    while True:
        try:
            res_detail = requests.get(DETAIL_STATUS_URL, headers=headers, timeout=30)
            res_detail.raise_for_status()
            detail_data = res_detail.json().get("executing", {})

            if not detail_data:
                print("🟡 Execution not started yet or still initializing...", flush=True)
                time.sleep(10)
                continue

            running_steps = 0
            for feature, scenarios in detail_data.items():
                print(f"\nFeature: {feature}", flush=True)
                for scenario_name, steps in scenarios.items():
                    print(f"  Scenario: {scenario_name}", flush=True)
                    for step in steps:
                        keyword = step.get("keyword", "")
                        name = step.get("name", "Unknown Step")
                        status = str(step.get("status", "unknown")).lower()
                        duration = step.get("duration", "N/A")
                        timestamp = step.get("timestamp", "N/A")

                        if status == "running":
                            running_steps += 1

                        print(f"    {keyword} {name} → {status.upper()} (Duration: {duration}, Timestamp: {timestamp})", flush=True)

            if running_steps == 0:
                print("\n✅ Execution completed.\n", flush=True)
                break
            else:
                print(f"\n🟡 Still running... {running_steps} steps in progress. Waiting 10s...\n", flush=True)
                time.sleep(10)

        except requests.exceptions.RequestException as e:
            print(f"⚠️ Polling error: {e}, retrying in 10s", flush=True)
            time.sleep(10)

    total_passed, total_failed = 0, 0
    for feature, scenarios in detail_data.items():
        for scenario_name, steps in scenarios.items():
            for step in steps:
                status = str(step.get("status", "unknown")).lower()
                if status == "passed":
                    total_passed += 1
                elif status == "failed":
                    total_failed += 1

    print(f"📊 High-Level Summary: Passed={total_passed}, Failed={total_failed}\n", flush=True)


def get_artifact_folder(exec_id=None):
    """Fetch artifact folder reliably, either by execution ID or latest."""
    folder_name = None

    if exec_id:
        res = requests.get(ARTIFACT_BY_EXEC_URL, headers=headers, params={"executionId": exec_id})
        if res.ok and res.json().get("data"):
            folder_name = res.json()["data"].get("folderName")

    # If per-execution artifact not found, fallback to latest artifact
    if not folder_name:
        res_latest = requests.get(LATEST_ARTIFACT_URL, headers=headers)
        res_latest.raise_for_status()
        latest_data = res_latest.json().get("data", {})
        folder_name = latest_data.get("latest_artifact_timestamp")
        artifact_url = latest_data.get("artifact_urls", [None])[0]
        if folder_name:
            print(f"ℹ️ Latest artifact: {folder_name}")
            if artifact_url:
                print(f"🔗 Artifact GUI URL: {artifact_url}")

    return folder_name


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

def fetch_artifact_summary(folder):
    """
    Fetch ABot artifact feature summary using execFeatureSummary API.
    Handles both single-feature dict and list of features.
    """
    print(f"\n📋 Fetching feature summary for artifact: {folder}\n")
    page = 1
    limit = 9999
    params = {"foldername": folder, "page": page, "limit": limit}

    try:
        res = requests.get(f"{ABOT_URL}/abot/api/v5/artifacts/execFeatureSummary", headers=headers, params=params, timeout=30)
        res.raise_for_status()
        data = res.json()

        if data.get("status", "").lower() != "ok":
            print(f"⚠️ Failed to fetch feature summary: {data.get('message')}")
            return

        summary_result = data.get("feature_summary", {}).get("result", {})

        # Wrap in list if it's a dict
        if isinstance(summary_result, dict):
            summary_list = [summary_result]
        elif isinstance(summary_result, list):
            summary_list = summary_result
        else:
            print("⚠️ Unexpected format of feature summary.")
            return

        for feature_item in summary_list:
            feature_data_list = feature_item.get("data", [])
            
            # Make sure feature_data_list is a list
            if isinstance(feature_data_list, dict):
                feature_data_list = [feature_data_list]
            elif not isinstance(feature_data_list, list):
                print("⚠️ Unexpected format inside data")
                continue

            for feature_data in feature_data_list:
                feature_name = feature_data.get("featureName", "Unknown Feature")
                steps = feature_data.get("steps", {})
                scenarios = steps.get("scenario", {})
                features = steps.get("features", {})
                
                print(f"Feature: {feature_name}")
                print(f"  Feature Status: {features.get('status', 'N/A').upper()} | Duration: {features.get('duration', 'N/A')}s")
                print(f"  Total Scenarios: {scenarios.get('total', 'N/A')} | Passed: {scenarios.get('passed', 'N/A')} | Failed: {scenarios.get('failed', 'N/A')}")
                total_steps = steps.get("steps", {})
                print(f"  Total Steps: {total_steps.get('total', 'N/A')} | Passed: {total_steps.get('passed', 'N/A')} | Failed: {total_steps.get('failed', 'N/A')} | Skipped: {total_steps.get('skipped', 'N/A')}")
                
                ue_summary = feature_data.get("totalUEPassFail", {})
                if ue_summary:
                    print(f"  UE Summary: Passed={ue_summary.get('passed', 'N/A')} | Failed={ue_summary.get('failed', 'N/A')}")

    except requests.exceptions.RequestException as e:
        print(f"⚠️ Error fetching feature summary: {e}")


# --- In your main __name__ block, call this after downloading the log ---
if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')

    login()
    update_config()
    exec_marker = execute_feature()
    real_exec_id = wait_for_new_execution(exec_marker)
    poll_current_status(real_exec_id)

    folder = get_artifact_folder(real_exec_id)
    if folder:
        download_and_print_log(folder)
        fetch_artifact_summary(folder)   # <-- NEW: Fetch and print feature summary

    print("=== ABot Test Automation Finished ===")




    print("=== ABot Test Automation Finished ===")
