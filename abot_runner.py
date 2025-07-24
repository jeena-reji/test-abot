import requests, time, sys, json

ABOT_URL = "http://10.176.27.73/abotrest"
LOGIN_URL = f"{ABOT_URL}/abot/api/v5/login"
CONFIG_URL = f"{ABOT_URL}/abot/api/v5/update_config_properties"
EXECUTE_URL = f"{ABOT_URL}/abot/api/v5/feature_files/execute"
STATUS_URL = f"{ABOT_URL}/abot/api/v5/execution_status"
ARTIFACT_URL = f"{ABOT_URL}/abot/api/v5/latest_artifact_name"
SUMMARY_URL = f"{ABOT_URL}/abot/api/v5/artifacts/execFeatureSummary"

USERNAME = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"
FEATURE_TAG = "3GPP-23401-4G"
CONFIG_FILE = "/etc/rebaca-test-suite/config/admin/ABotConfig.properties"

headers = {"Content-Type": "application/json"}

def login():
    print("🔐 Logging in...")
    payload = {"email": USERNAME, "password": PASSWORD, "expires": False}
    res = requests.post(LOGIN_URL, json=payload)
    res.raise_for_status()
    token = res.json()["data"]["token"]
    headers["Authorization"] = f"Bearer {token}"
    print("✅ Login successful.")
    return token

def update_config():
    print("⚙️ Updating config...")
    payload = {
        "uncomment": [
            "ABOT.SUTVARS=file:abot-emulated/sut-vars/default.properties"
        ],
        "comment": [
            "ABOT.SUTVARS=file:abot-emulated/sut-vars/default5g.properties",
            "ABOT.SUTVARS=file:abot-emulated/sut-vars/default4g5g.properties",
            "ABOT.SUTVARS.ORAN=file:abot-emulated/sut-vars/default5g-oran.properties"
        ],
        "update": {}
    }
    res = requests.post(CONFIG_URL, headers=headers, json=payload, params={"filename": CONFIG_FILE})
    res.raise_for_status()
    print("✅ Config updated.")

def execute_feature():
    print(f"🚀 Executing feature tag: {FEATURE_TAG}")
    payload = {
        "params": {
            "tag": FEATURE_TAG,
            "env": "default",
            "parallel": False,
            "video": False
        }
    }
    res = requests.post(EXECUTE_URL, headers=headers, json=payload)
    res.raise_for_status()
    print("▶️ Test started.")


def poll_status():
    print("⏳ Polling execution status...")
    while True:
        res = requests.get(STATUS_URL, headers=headers)
        res.raise_for_status()
        json_data = res.json()
        print("🧪 Raw /execution_status response:")
        print(json.dumps(json_data, indent=2))

        if "executing" in json_data:
            exec_status = json_data["executing"]
            if not exec_status.get("status", False):
                print("✅ Execution completed.")
                return
            else:
                print("🟡 Still running... waiting 10s")
        else:
            print("⚠️ Unexpected execution_status structure, retrying...")

        time.sleep(10)



def get_artifact_folder():
    res = requests.get(ARTIFACT_URL, headers=headers)
    res.raise_for_status()
    folder = res.json()["data"]["latest_artifact_timestamp"]
    print(f"📁 Latest artifact folder: {folder}")
    return folder

def get_summary(folder):
    print("📊 Fetching execution summary...")
    params = {"foldername": folder, "page": 1, "limit": 9998}
    res = requests.get(SUMMARY_URL, headers=headers, params=params)
    res.raise_for_status()
    summary = res.json()
    with open("execution_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    return summary

def check_result(summary):
    if "feature_summary" not in summary:
        print("❌ Error: 'feature_summary' not present in summary.")
        print("Full summary response:", summary)
        sys.exit(1)

    result = summary["feature_summary"]["result"]
    failed = result["totalScenarios"]["totalScenariosFailed"]["totalScenariosFailedNumber"]
    if failed > 0:
        print(f"❌ Test failed: {failed} scenario(s) failed.")
        sys.exit(1)
    else:
        print("✅ All test scenarios passed.")




if __name__ == "__main__":
    login()
    update_config()
    execute_feature()
    poll_status()
    folder = get_artifact_folder()
    if not folder:
        print("❌ No artifact folder returned. Cannot fetch summary.")
        sys.exit(1)
    summary = get_summary(folder)
    check_result(summary)
