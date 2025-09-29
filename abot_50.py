import requests, time, os, json
from urllib.parse import quote

# ----------------- COLORS -----------------
class Colors:
    GREEN = "\033[92m"   # Bright green
    RED = "\033[91m"     # Bright red
    YELLOW = "\033[93m"  # Yellow
    RESET = "\033[0m"    # Reset to default color

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

USERNAME = os.getenv("ABOT_USER")
PASSWORD = os.getenv("ABOT_PASS")
FEATURE_TAG = os.getenv("FEATURE_TAG", "5gs-initial-registration-sdcore-0.0.10")

headers = {"Content-Type": "application/json"}


# ----------------- FUNCTIONS -----------------
def login():
    print("Logging in...")
    payload = {"email": USERNAME, "password": PASSWORD, "expires": False}
    res = requests.post(LOGIN_URL, json=payload)
    res.raise_for_status()
    token = res.json()["data"]["token"]
    headers["Authorization"] = f"Bearer {token}"
    print("Login successful.\n")


def update_config():
    print("=== Configuration Phase ===")
    payload1 = {"update": {"ABOT.SUTVARS.ORAN": "", "ABOT.SUTVARS": "file:IOSMCN/sut-vars/default5G.properties"}}
    params1 = {"filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABotConfig.properties"}
    requests.post(CONFIG_URL, headers=headers, json=payload1, params=params1, timeout=30).raise_for_status()
    print(" Updated sut-vars → ABotConfig.properties")

    payload2 = {"update": {"ABOT.TESTBED": "file:IOSMCN/testbeds/testbed-5G-IOSMCN.properties", "LOAD_SWITCH": "off"}}
    params2 = {"filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABot_System_Configs/ABotConfig_Primary_Configuration.properties"}
    requests.post(CONFIG_URL, headers=headers, json=payload2, params=params2, timeout=30).raise_for_status()
    print(" Updated testbed → ABot_Primary_Configuration.properties\n")
    time.sleep(2)


def execute_feature():
    print(f"Executing feature tag: {FEATURE_TAG}")
    payload = {"params": FEATURE_TAG, "build": "default-build"}
    res = requests.post(EXECUTE_URL, headers=headers, json=payload)
    res.raise_for_status()
    print("Test started.\n")
    time.sleep(2)
    return FEATURE_TAG


def wait_for_new_execution(feature_tag):
    print(f" Waiting for ABot to switch to execution {feature_tag}...")
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
                    print(f"Execution is running...")
                    running_shown = True
            else:
                print(f"Execution finished: {current_id} (tag={current_name})")
                return current_id
        time.sleep(5)


def poll_current_status(exec_id):
    print("Polling execution status...\n", flush=True)

    while True:
        try:
            res_detail = requests.get(DETAIL_STATUS_URL, headers=headers, timeout=30)
            res_detail.raise_for_status()
            detail_data = res_detail.json().get("executing", {})

            if not detail_data:
                print("Execution not started yet or still initializing...", flush=True)
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

                        # Color coding for status
                        if status == "passed":
                            color = Colors.GREEN
                        elif status == "failed":
                            color = Colors.RED
                        elif status == "running":
                            color = Colors.YELLOW
                        else:
                            color = Colors.RESET

                        if status == "running":
                            running_steps += 1

                        # Print with colored status
                        print(f"    {keyword} {name} → {color}{status.upper()}{Colors.RESET} (Duration: {duration}, Timestamp: {timestamp})", flush=True)

            if running_steps == 0:
                print("\nExecution completed.\n", flush=True)
                break
            else:
                print(f"\n Still running... {running_steps} steps in progress. Waiting 10s...\n", flush=True)
                time.sleep(10)

        except requests.exceptions.RequestException as e:
            print(f"Polling error: {e}, retrying in 10s", flush=True)
            time.sleep(10)

    # -----------------------
    # Summary calculation
    # -----------------------
    total_steps_passed = total_steps_failed = total_steps_skipped = 0
    total_scenarios_passed = total_scenarios_failed = 0

    for feature, scenarios in detail_data.items():
        for scenario_name, steps in scenarios.items():
            scenario_failed = False
            for step in steps:
                status = step.get("status", "").lower()
                if status == "passed":
                    total_steps_passed += 1
                elif status == "failed":
                    total_steps_failed += 1
                    scenario_failed = True
                elif status == "skipped":
                    total_steps_skipped += 1

            if scenario_failed:
                total_scenarios_failed += 1
            else:
                total_scenarios_passed += 1

    print(f"\nHigh-Level Summary (Steps): Passed={total_steps_passed}, Failed={total_steps_failed}, Skipped={total_steps_skipped}")
    print(f"High-Level Summary (Scenarios): Passed={total_scenarios_passed}, Failed={total_scenarios_failed}\n", flush=True)


def wait_for_latest_artifact_by_tag(feature_tag, timeout=300):
    start_time = time.time()
    latest_folder = None

    while time.time() - start_time < timeout:
        try:
            res_latest = requests.get(LATEST_ARTIFACT_URL, headers=headers)
            res_latest.raise_for_status()
            latest_data = res_latest.json().get("data", {})
            folder_name = latest_data.get("latest_artifact_timestamp")
            if folder_name and feature_tag in folder_name:
                if folder_name != latest_folder:
                    print(f" Found latest artifact folder: {folder_name}")
                    latest_folder = folder_name
                return latest_folder
        except requests.exceptions.RequestException:
            pass
        time.sleep(5)

    print(f" Artifact for tag '{feature_tag}' not found in {timeout}s")
    return None


def download_and_print_log(folder):
    safe_folder = quote(folder)
    try:
        res = requests.get(LOG_URL, headers=headers, params={"foldername": safe_folder})
        if res.status_code != 200:
            return
        res.raise_for_status()
        log_text = res.text
        with open("abot_log.log", "w") as f:
            f.write(log_text)
    except requests.exceptions.RequestException:
        return


def fetch_feature_details(folder, feature_id, feature_name):
    params = {
        "foldername": folder,
        "featureId": feature_id,
        "featurename": feature_name
    }
    try:
        res = requests.get(EXEC_FEATURE_DETAILS, headers=headers, params=params, timeout=30)
        res.raise_for_status()
        print(json.dumps(res.json(), indent=2))
    except requests.exceptions.RequestException as e:
        print(f" Error fetching feature details for {feature_id}: {e}")


def fetch_all_feature_details(folder, timeout=60):
    print(f"\n Fetching all feature details for artifact: {folder}\n")
    page = 1
    limit = 9999
    params = {"foldername": folder, "page": page, "limit": limit}

    try:
        res = requests.get(f"{ABOT_URL}/abot/api/v5/artifacts/execFeatureSummary",
                           headers=headers, params=params, timeout=30)
        res.raise_for_status()
        data = res.json()

        if data.get("status", "").lower() != "ok":
            print(f" Failed to fetch feature summary: {data.get('message')}")
            return

        summary_result = data.get("feature_summary", {}).get("result", [])
        if isinstance(summary_result, dict):
            summary_result = [summary_result]

        feature_files = []
        for feature_item in summary_result:
            feature_data_list = feature_item.get("data", [])
            if isinstance(feature_data_list, dict):
                feature_data_list = [feature_data_list]
            for feature_data in feature_data_list:
                feature_id = feature_data.get("featureFileName") or feature_data.get("featureId")
                feature_name = feature_data.get("featureName")
                if feature_id and feature_name:
                    feature_files.append((feature_id, feature_name))

        if not feature_files:
            print(" No feature files found in artifact.")
            return

        for feature_id, feature_name in feature_files:
            print(f"\n==== Fetching details for {feature_id} ({feature_name}) ====")
            fetch_feature_details(folder, feature_id, feature_name)

    except requests.exceptions.RequestException as e:
        print(f" Error fetching feature list: {e}")


# ----------------- MAIN -----------------
if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')

    login()
    update_config()
    exec_marker = execute_feature()
    real_exec_id = wait_for_new_execution(exec_marker)
    poll_current_status(real_exec_id)

    folder = wait_for_latest_artifact_by_tag(FEATURE_TAG, timeout=300)
    if folder:
        download_and_print_log(folder)
        fetch_all_feature_details(folder)

    print("=== ABot Test Automation Finished ===")
