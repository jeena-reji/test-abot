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
ARTIFACT_URL = f"{ABOT_URL}/abot/api/v5/artifacts"
LATEST_ARTIFACT_URL = f"{ABOT_URL}/abot/api/v5/latest_artifact_name"
ARTIFACT_DOWNLOAD_URL = f"{ABOT_URL}/abot/api/v5/artifacts/download"
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
    res = requests.post(LOGIN_URL, json=payload, timeout=30)
    res.raise_for_status()
    token = res.json().get("data", {}).get("token")
    if not token:
        print(f"❌ Login response missing token: {res.text}")
        sys.exit(1)
    headers["Authorization"] = f"Bearer {token}"
    print("✔ Login successful.")


def update_config():
    print("=== Configuration Phase ===")
    payload1 = {
        "update": {
            "ABOT.SUTVARS.ORAN": "",
            "ABOT.SUTVARS": "file:IOSMCN/sut-vars/default5G.properties"
        }
    }
    params1 = {
        "filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABotConfig.properties"
    }
    requests.post(CONFIG_URL, headers=headers, json=payload1, params=params1, timeout=30).raise_for_status()
    print("✔ Updated sut-vars → ABotConfig.properties")

    payload2 = {
        "update": {
            "ABOT.TESTBED": "file:IOSMCN/testbeds/testbed-5G-IOSMCN.properties",
            "LOAD_SWITCH": "off"
        }
    }
    params2 = {
        "filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABot_System_Configs/ABotConfig_Primary_Configuration.properties"
    }
    requests.post(CONFIG_URL, headers=headers, json=payload2, params=params2, timeout=30).raise_for_status()
    print("✔ Updated testbed → ABot_Primary_Configuration.properties")
    time.sleep(5)


def wait_for_system_ready():
    print("Waiting for system to be ready after config...")
    time.sleep(10)


def execute_feature():
    print(f"Executing feature tag: {FEATURE_TAG}")
    payload = {"params": FEATURE_TAG}
    res = requests.post(EXECUTE_URL, headers=headers, json=payload, timeout=30)
    res.raise_for_status()
    print("✔ Test execution started.")
    try:
        print("Execution response:", json.dumps(res.json(), indent=2))
    except Exception:
        print("Raw execution response:", res.text)


def poll_status():
    print("Polling execution status...")
    while True:
        res = requests.get(STATUS_URL, headers=headers, timeout=30)
        res.raise_for_status()
        exec_info = res.json().get("executing", {})

        executing_list = exec_info.get("executing", [])
        statuses = exec_info.get("execution_status", [])

        # filter only for this FEATURE_TAG
        filtered_execs = [e for e in executing_list if FEATURE_TAG in e.get("name", "")]
        filtered_statuses = [s for s in statuses if FEATURE_TAG in s.get("name", "") or s.get("name") == "execution completed"]

        print("Execution status for current tag:")
        print(json.dumps(filtered_execs, indent=2))
        print(json.dumps(filtered_statuses, indent=2))

        if any(s["name"] == "execution completed" and s["status"] == 1 for s in filtered_statuses):
            print("✔ ABot reports execution completed.")
            return

        print("Still running in ABot... waiting 10s")
        time.sleep(10)


def get_artifact_folder():
    print("Fetching artifact folder...")
    for _ in range(20):
        res = requests.get(ARTIFACT_URL, headers=headers, timeout=30)
        res.raise_for_status()
        all_data = res.json().get("data", [])

        matching = []
        for item in all_data:
            if isinstance(item, dict):
                if FEATURE_TAG in item.get("label", ""):
                    matching.append(item)
            elif isinstance(item, str):
                if FEATURE_TAG in item:
                    matching.append({"label": item, "epoch_time": 0})

        if matching:
            folder = sorted(matching, key=lambda x: x.get("epoch_time", 0))[-1]
            print(f"✔ Found matching artifact: {folder['label']}")
            return folder["label"]

        print(f"⚠ No artifact yet for tag {FEATURE_TAG}, retrying...")
        time.sleep(10)

    print("❌ Could not find matching artifact folder for this tag.")
    sys.exit(1)


def download_artifact(folder: str):
    if not folder:
        print("❌ No artifact folder provided, cannot download.")
        return
    print(f"Downloading artifact for folder: {folder}")
    params = {"path": folder}
    res = requests.get(ARTIFACT_DOWNLOAD_URL, headers=headers, params=params, timeout=120, stream=True)
    res.raise_for_status()
    out_file = "artifact.zip"
    with open(out_file, "wb") as f:
        for chunk in res.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    print(f"✔ Artifact downloaded and saved as {out_file}")


def get_summary(folder: str):
    if not folder:
        print("❌ No artifact folder available, cannot fetch summary.")
        return {}
    print("Fetching execution summary...")
    params = {"foldername": folder, "page": 1, "limit": 9998}
    res = requests.get(SUMMARY_URL, headers=headers, params=params, timeout=60)
    res.raise_for_status()
    summary = res.json()
    with open("execution_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))
    return summary


def check_result(summary: dict) -> bool:
    try:
        all_passed = True
        found_any = False
        features = summary.get("feature_summary", {}).get("result", {}).get("data", [])
        if isinstance(features, list) and features:
            found_any = True
            for f in features:
                status = (f.get("features", {}) or {}).get("status", "")
                name = f.get("featureName") or f.get("name") or "UnknownFeature"
                if str(status).lower() != "passed":
                    print(f"❌ Feature failed: {name} | status='{status}'")
                    all_passed = False
        if not found_any and isinstance(summary.get("data"), list):
            found_any = True
            for item in summary["data"]:
                if str(item.get("Status", "")).lower() == "fail":
                    print(f"❌ Failed test: {item.get('FeatureFileName', 'UnknownFeature')} | Reason: {item.get('ErrorMessage', 'N/A')}")
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


if __name__ == "__main__":
    try:
        print("=== ABot Test Automation Started ===")
        login()
        update_config()
        wait_for_system_ready()
        execute_feature()
        poll_status()
        folder = get_artifact_folder()
        download_artifact(folder)
        summary = get_summary(folder)
        test_passed = check_result(summary)

        # save artifact path for GitHub Actions
        with open("artifact_path.txt", "w") as f:
            f.write(str(folder))

        print("=== ABot Test Automation Completed ===")
        sys.exit(0 if test_passed else 1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
