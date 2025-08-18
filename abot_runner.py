import requests, time, sys, json ,os

ABOT_URL = "http://10.176.27.73/abotrest"
LOGIN_URL = f"{ABOT_URL}/abot/api/v5/login"
CONFIG_URL = f"{ABOT_URL}/abot/api/v5/update_config_properties"
EXECUTE_URL = f"{ABOT_URL}/abot/api/v5/feature_files/execute"
STATUS_URL = f"{ABOT_URL}/abot/api/v5/execution_status"
ARTIFACT_URL = f"{ABOT_URL}/abot/api/v5/latest_artifact_name"
SUMMARY_URL = f"{ABOT_URL}/abot/api/v5/artifacts/execFeatureSummary"

USERNAME = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"
FEATURE_TAG = "5gs-initial-registration-sdcore-0.0.10"

CONFIG_FILE = "/etc/rebaca-test-suite/config/admin/ABotConfig.properties"

headers = {"Content-Type": "application/json"}

def login():
    print("Logging in...")
    payload = {"email": USERNAME, "password": PASSWORD, "expires": False}
    res = requests.post(LOGIN_URL, json=payload)
    res.raise_for_status()
    token = res.json()["data"]["token"]
    headers["Authorization"] = f"Bearer {token}"
    print("Login successful.")
    return token

def update_config():
    print("Updating config...")
    payload = {
        "update": {
            "ABOT.TESTBED": "testbed-4g5g"
        }
    }
    res = requests.post(CONFIG_URL, headers=headers, json=payload, params={"filename": CONFIG_FILE})
    res.raise_for_status()
    print("Config updated to IOSMCN testbed (emulated-smf + sut-upf).")


def execute_feature():
    print(f"Executing feature tag: {FEATURE_TAG}")
    payload = {"params": FEATURE_TAG}
    res = requests.post(EXECUTE_URL, headers=headers, json=payload)
    res.raise_for_status()
    print("Test started.")

def poll_status():
    print("Polling execution status...")
    while True:
        res = requests.get(STATUS_URL, headers=headers)
        res.raise_for_status()
        json_data = res.json()
        print("Raw /execution_status response:")
        print(json.dumps(json_data, indent=2))

        
        # Make sure keys exist
        if "executing" in json_data and "executing" in json_data["executing"]:
            exec_list = json_data["executing"]["executing"]
            if exec_list and not exec_list[0].get("is_executing", False):
                print("Execution completed.")
                return
            else:
                print("Still running... waiting 10s")
        else:
            print("Unexpected execution_status structure, retrying...")
        
        time.sleep(10)


def get_artifact_folder():
    res = requests.get(ARTIFACT_URL, headers=headers)
    res.raise_for_status()
    folder = res.json()["data"]["latest_artifact_timestamp"]
    print(f"Latest artifact folder: {folder}")
    return folder

def get_summary(folder):
    print("Fetching execution summary...")
    params = {"foldername": folder, "page": 1, "limit": 9998}
    res = requests.get(SUMMARY_URL, headers=headers, params=params)
    res.raise_for_status()
    summary = res.json()
    with open("execution_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    return summary

def check_result(summary):
    result = summary["feature_summary"]["result"]
    failed = result["totalScenarios"]["totalScenariosFailed"]["totalScenariosFailedNumber"]
    if failed > 0:
        print(f"Test failed: {failed} scenario(s) failed.")
        with open("test_failed.txt", "w") as f:
            f.write(str(failed))
    else:
        print("All test scenarios passed.")


def download_and_print_log(folder):
    log_url = f"{ABOT_URL}/abot/api/v5/artifacts/logs"
    params = {"foldername": folder}
    print("Downloading ABot execution log...")
    res = requests.get(log_url, headers=headers, params=params)
    res.raise_for_status()

    log_text = res.text
    print("ABot Execution Log:\n")
    print(log_text)

    # Save to file as well
    with open("abot_log.log", "w") as f:
        f.write(log_text)


if __name__ == "__main__":
    login()
    update_config()
    execute_feature()
    poll_status()
    folder = get_artifact_folder()
    summary = get_summary(folder)
    check_result(summary)
    download_and_print_log(folder)

    # Save folder path for GitHub Actions
    with open("artifact_path.txt", "w") as f:
        f.write(folder)
