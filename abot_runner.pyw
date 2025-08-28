import requests, time, sys, json, os

ABOT_URL = "http://10.176.27.73/abotrest"

LOGIN_URL = f"{ABOT_URL}/abot/api/v5/login"
CONFIG_URL = f"{ABOT_URL}/abot/api/v5/update_config_properties"
EXECUTE_URL = f"{ABOT_URL}/abot/api/v5/feature_files/execute"
STATUS_URL = f"{ABOT_URL}/abot/api/v5/execution_status"
ARTIFACT_URL = f"{ABOT_URL}/abot/api/v5/latest_artifact_name"
SUMMARY_URL = f"{ABOT_URL}/abot/api/v5/artifacts/execFeatureSummary"

USERNAME = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"
FEATURE_TAG = "@5gs-initial-registration-with-integrity-and-ciphering-sdcore-0.1.2"

headers = {"Content-Type": "application/json"}


def login():
    print("Logging in...")
    payload = {"email": USERNAME, "password": PASSWORD, "expires": False}
    try:
        res = requests.post(LOGIN_URL, json=payload, timeout=30)
        res.raise_for_status()
        token = res.json()["data"]["token"]
        headers["Authorization"] = f"Bearer {token}"
        print("✔ Login successful.")
        return token
    except Exception as e:
        print(f"❌ Login failed: {e}")
        sys.exit(1)


def update_config():
    print("=== Configuration Phase ===")
    try:
        payload1 = {
            "update": {
                "ABOT.SUTVARS.ORAN": "",
                "ABOT.SUTVARS": "file:IOSMCN/sut-vars/default5G.properties",
            }
        }
        params1 = {
            "filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABotConfig.properties"
        }
        res1 = requests.post(CONFIG_URL, headers=headers, json=payload1, params=params1, timeout=30)
        res1.raise_for_status()
        print("✔ Updated sut-vars → ABotConfig.properties")

        payload2 = {
            "update": {
                "ABOT.TESTBED": "file:IOSMCN/testbeds/testbed-5G-IOSMCN.properties",
                "LOAD_SWITCH": "off",
            }
        }
        params2 = {
            "filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABot_System_Configs/ABotConfig_Primary_Configuration.properties"
        }
        res2 = requests.post(CONFIG_URL, headers=headers, json=payload2, params=params2, timeout=30)
        res2.raise_for_status()
        print("✔ Updated testbed → ABot_Primary_Configuration.properties")

        time.sleep(5)
    except Exception as e:
        print(f"❌ Config update failed: {e}")
        sys.exit(1)


def wait_for_system_ready():
    print("Waiting for system to be ready after config...")
    time.sleep(10)


def execute_feature():
    print(f"Executing feature tag: {FEATURE_TAG}")
    payload = {"feature_tags": [FEATURE_TAG]}
    try:
        res = requests.post(EXECUTE_URL, headers=headers, json=payload, timeout=30)
        res.raise_for_status()
        data = res.json().get("data", {})
        exec_id = data.get("execution_id")
        print(f"✔ Test execution started with ID: {exec_id}")
        return exec_id
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        sys.exit(1)


def poll_status(exec_id):
    print(f"Polling execution status for ID: {exec_id}...")
    max_attempts = 180
    for attempt in range(max_attempts):
        try:
            res = requests.get(f"{STATUS_URL}/{exec_id}", headers=headers, timeout=30)
            res.raise_for_status()
            json_data = res.json()
            print(f"Status check #{attempt + 1}")
            print(json.dumps(json_data, indent=2))

            executing = json_data.get("executing", {}).get("executing", [])
            if executing:
                if not executing[0].get("is_executing", False):
                    print("✔ Execution completed.")
                    return
                else:
                    print("Still running... wait 10s")
            else:
                print("No execution found, assuming finished.")
                return
        except Exception as e:
            print(f"⚠ Status check failed: {e}")
        time.sleep(10)
    print("⚠ Max wait time reached, moving to results.")


def get_artifact_folder():
    try:
        res = requests.get(ARTIFACT_URL, headers=headers, timeout=30)
        res.raise_for_status()
        folder = res.json()["data"]["latest_artifact_timestamp"]
        print(f"✔ Latest artifact folder: {folder}")
        return folder
    except Exception as e:
        print(f"❌ Failed to get artifact folder: {e}")
        sys.exit(1)


def get_summary(folder):
    print("Fetching execution summary...")
    params = {"foldername": folder, "page": 1, "limit": 9998}
    try:
        res = requests.get(SUMMARY_URL, headers=headers, params=params, timeout=30)
        res.raise_for_status()
        summary = res.json()
        with open("execution_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        return summary
    except Exception as e:
        print(f"❌ Failed to get summary: {e}")
        sys.exit(1)


def check_result(summary):
    try:
        if "data" in summary and isinstance(summary["data"], list):
            failed = False
            for item in summary["data"]:
                if item.get("Status", "").lower() == "fail":
                    failed = True
                    with open("test_failed.txt", "w") as f:
                        f.write("One or more tests failed\n")
            if failed:
                print("❌ Test failed")
                return False
            else:
                print("✔ All tests passed")
                return True
        else:
            print("⚠ Summary format unexpected, marking as failed")
            return False
    except Exception as e:
        print(f"⚠ check_result error: {e}")
        return False


def analyze_execution_failure(summary):
    print("=== Failure Analysis ===")
    if "data" in summary:
        for item in summary["data"]:
            if item.get("Status", "").lower() == "fail":
                print(f"- Failed test: {item.get('FeatureFileName', 'Unknown')} | Reason: {item.get('ErrorMessage', 'N/A')}")


if __name__ == "__main__":
    try:
        print("=== ABot Test Automation Started ===")
        login()
        update_config()
        wait_for_system_ready()
        exec_id = execute_feature()
        poll_status(exec_id)
        folder = get_artifact_folder()
        summary = get_summary(folder)
        test_passed = check_result(summary)
        if not test_passed:
            analyze_execution_failure(summary)

        # Save artifact folder for GitHub Actions
        with open("artifact_path.txt", "w") as f:
            f.write(folder)

        print("=== ABot Test Automation Completed ===")
        sys.exit(0 if test_passed else 1)

    except KeyboardInterrupt:
        print("❌ Interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
