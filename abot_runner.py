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
ARTIFACT_URL = f"{ABOT_URL}/abot/api/v5/latest_artifact_name"
SUMMARY_URL = f"{ABOT_URL}/abot/api/v5/artifacts/execFeatureSummary"

# Credentials and feature tag
USERNAME = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"
FEATURE_TAG = os.getenv("FEATURE_TAG", "5gs-initial-registration-with-integrity-and-ciphering-sdcore-0.1.2")

# Request headers
headers = {"Content-Type": "application/json"}


def login():
    print("Logging in...")
    payload = {"email": USERNAME, "password": PASSWORD, "expires": False}
    try:
        res = requests.post(LOGIN_URL, json=payload, timeout=30)
        res.raise_for_status()
        token = res.json().get("data", {}).get("token")
        if not token:
            print(f"❌ Login response missing token: {res.text}")
            sys.exit(1)
        headers["Authorization"] = f"Bearer {token}"
        print("✔ Login successful.")
        return token
    except requests.exceptions.RequestException as e:
        print(f"❌ Login failed: {e}")
        sys.exit(1)


def update_config():
    print("=== Configuration Phase ===")
    try:
        # 1️⃣ First update: sut-vars
        payload1 = {
            "update": {
                "ABOT.SUTVARS.ORAN": "",
                "ABOT.SUTVARS": "file:IOSMCN/sut-vars/default5G.properties"
            }
        }
        params1 = {
            "filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABotConfig.properties"
        }
        res1 = requests.post(CONFIG_URL, headers=headers, json=payload1, params=params1, timeout=30)
        res1.raise_for_status()
        print("✔ Updated sut-vars → ABotConfig.properties")

        # 2️⃣ Second update: testbed + load switch
        payload2 = {
            "update": {
                "ABOT.TESTBED": "file:IOSMCN/testbeds/testbed-5G-IOSMCN.properties",
                "LOAD_SWITCH": "off"
            }
        }
        params2 = {
            "filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABot_System_Configs/ABotConfig_Primary_Configuration.properties"
        }
        res2 = requests.post(CONFIG_URL, headers=headers, json=payload2, params=params2, timeout=30)
        res2.raise_for_status()
        print("✔ Updated testbed → ABot_Primary_Configuration.properties")

        # Allow propagation
        time.sleep(5)

    except requests.exceptions.RequestException as e:
        print(f"❌ Config update failed: {e}")
        sys.exit(1)


def wait_for_system_ready():
    print("Waiting for system to be ready after config...")
    time.sleep(10)


def execute_feature():
    print(f"Executing feature tag: {FEATURE_TAG}")
    payload = {"params": FEATURE_TAG}
    try:
        res = requests.post(EXECUTE_URL, headers=headers, json=payload, timeout=30)
        res.raise_for_status()
        print("✔ Test execution started.")
        if res.text:
            try:
                print("Execution response:", json.dumps(res.json(), indent=2))
            except json.JSONDecodeError:
                print("Raw execution response:", res.text)
    except requests.exceptions.RequestException as e:
        print(f"❌ Test execution failed: {e}")
        sys.exit(1)


def poll_status():
    print("Polling execution status...")
    while True:
        try:
            res = requests.get(STATUS_URL, headers=headers, timeout=30)
            res.raise_for_status()
            json_data = res.json()
            exec_info = json_data.get("executing", {})


            # ✅ Filter only executions matching FEATURE_TAG
            executing_list = exec_info.get("executing", [])
            filtered_execs = [e for e in executing_list if FEATURE_TAG in e.get("name", "")]
            
            
            statuses = exec_info.get("execution_status", [])
            
            
            print("Execution status for current tag:")
            print(json.dumps(filtered_execs, indent=2))
            print(json.dumps(statuses, indent=2))
            
            
            if any(s["name"] == "execution completed" and s["status"] == 1 for s in statuses):
                print("✔ ABot reports execution completed.")
                return
            
            
            print("Still running in ABot... waiting 10s")
        except Exception as e:
            print(f"⚠ Status check failed: {e}")
        time.sleep(10)

def get_artifact_folder(max_retries: int = 6, wait_seconds: int = 5):
    """Get latest artifact folder. Retry briefly because the folder can lag execution completion."""
    for attempt in range(1, max_retries + 1):
        try:
            res = requests.get(ARTIFACT_URL, headers=headers, timeout=30)
            res.raise_for_status()
            data = res.json().get("data", {})
            folder = data.get("latest_artifact_timestamp")

            if not folder:
                raise ValueError(f"latest_artifact_timestamp missing in response: {res.text}")

            if FEATURE_TAG not in folder:
                print(f"⚠ Latest folder '{folder}' does not exactly contain tag '{FEATURE_TAG}', using it anyway.")

            print(f"✔ Latest artifact folder: {folder}")
            return folder

        except Exception as e:
            print(f"⚠ Attempt {attempt}/{max_retries} to fetch artifact folder failed: {e}")
            if attempt < max_retries:
                time.sleep(wait_seconds)
            else:
                print("❌ Could not retrieve artifact folder after retries.")
                sys.exit(1)



def get_summary(folder: str):
    if not folder:
        print("❌ No artifact folder available, cannot fetch summary.")
        return {}

    print("Fetching execution summary...")
    params = {"foldername": folder, "page": 1, "limit": 9998}
    try:
        res = requests.get(SUMMARY_URL, headers=headers, params=params, timeout=60)
        res.raise_for_status()
        summary = res.json()

        # Persist raw summary for debugging
        with open("execution_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        print(json.dumps(summary, indent=2))
        return summary
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to get summary: {e}")
        return {}  # Let caller mark as failed


def check_result(summary: dict) -> bool:
    """Return True only if ALL features/tests passed. Handles multiple ABot summary shapes."""
    try:
        all_passed = True
        found_any = False

        # Shape A: summary.feature_summary.result.data[*].features.status
        result = summary.get("feature_summary", {}).get("result", {})
        features = result.get("data", [])
        if isinstance(features, list) and features:
            found_any = True
            for f in features:
                status = (f.get("features", {}) or {}).get("status", "")
                name = f.get("featureName") or f.get("name") or "UnknownFeature"
                if str(status).lower() != "passed":
                    print(f"❌ Feature failed: {name} | status='{status}'")
                    all_passed = False

        # Shape B: summary.data[*] with "Status" and optional "ErrorMessage"
        if not found_any and isinstance(summary.get("data"), list):
            found_any = True
            for item in summary["data"]:
                status = str(item.get("Status", "")).lower()
                if status == "fail":
                    fname = item.get("FeatureFileName", "UnknownFeature")
                    reason = item.get("ErrorMessage", "N/A")
                    print(f"❌ Failed test: {fname} | Reason: {reason}")
                    all_passed = False

        if not found_any:
            print("⚠ No features found in summary, marking failed")
            return False

        if all_passed:
            print("✔ All features passed")
        return all_passed

    except Exception as e:
        print(f"⚠ check_result error: {e}")
        return False



def analyze_execution_failure(summary: dict):
    """Best-effort failure details to help debugging."""
    try:
        print("=== Failure Analysis ===")
        # From Shape A
        for f in (summary.get("feature_summary", {}).get("result", {}).get("data", []) or []):
            status = (f.get("features", {}) or {}).get("status", "")
            if str(status).lower() != "passed":
                print(f"- Feature: {f.get('featureName', 'Unknown')} | status={status}")
        # From Shape B
        if isinstance(summary.get("data"), list):
            for item in summary["data"]:
                if str(item.get("Status", "")).lower() == "fail":
                    print(f"- Failed test: {item.get('FeatureFileName', 'Unknown')} | Reason: {item.get('ErrorMessage', 'N/A')}")
    except Exception as e:
        print(f"⚠ analyze_execution_failure error: {e}")

def download_and_print_log(folder: str):
    """Stub for future: download/print logs for debugging."""
    print(f"📂 Logs for artifact folder {folder} would be downloaded/printed here.")


if __name__ == "__main__":
    try:
        print("=== ABot Test Automation Started ===")
        login()
        update_config()
        wait_for_system_ready()
        execute_feature()
        poll_status()
        folder = get_artifact_folder()
        summary = get_summary(folder)
        test_passed = check_result(summary)
        if not test_passed:
            analyze_execution_failure(summary)
        download_and_print_log(folder)

        # Write artifact path only if we have one
        if folder:
            with open("artifact_path.txt", "w") as f:
                f.write(str(folder))

        print("=== ABot Test Automation Completed ===")
        sys.exit(0 if test_passed else 1)

    except KeyboardInterrupt:
        print("❌ Interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
