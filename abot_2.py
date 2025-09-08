import requests, time, sys, json, os, urllib.parse
from datetime import datetime

# ----------------- CONFIG -----------------
ABOT_URL = "http://10.176.27.73/abotrest"
LOGIN_URL = f"{ABOT_URL}/abot/api/v5/login"
CONFIG_URL = f"{ABOT_URL}/abot/api/v5/update_config_properties"
EXECUTE_URL = f"{ABOT_URL}/abot/api/v5/feature_files/execute"
STATUS_URL = f"{ABOT_URL}/abot/api/v5/execution_status"
ARTIFACT_URL = f"{ABOT_URL}/abot/api/v5/latest_artifact_name"
SUMMARY_URL = f"{ABOT_URL}/abot/api/v5/artifacts/execFeatureSummary"

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
    return token

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

        exec_list = json_data.get("executing", {}).get("executing", [])
        if exec_list and not exec_list[0].get("is_executing", True):
            print("✅ Execution completed.")
            return
        else:
            print("🟡 Still running... waiting 10s")
        time.sleep(10)

def get_latest_artifact():
    """Fetch the latest artifact name and URL from ABot."""
    res = requests.get(ARTIFACT_URL, headers=headers)
    res.raise_for_status()
    data = res.json()["data"]
    
    latest_artifact_name = data["latest_artifact_timestamp"]
    artifact_urls = data.get("artifact_urls", [])

    print(f"📁 Latest artifact name: {latest_artifact_name}")
    if artifact_urls:
        print(f"🔗 Artifact GUI URL: {artifact_urls[0]}")
    else:
        print("⚠️ No artifact URL available.")

    return latest_artifact_name

def download_and_print_log(folder):
    """Download ABot execution log using URL-encoded folder name."""
    log_url = f"{ABOT_URL}/abot/api/v5/artifacts/logs"
    encoded_folder = urllib.parse.quote(folder, safe='')  # Encode special characters
    params = {"foldername": encoded_folder}

    print("📥 Downloading ABot execution log...")
    res = requests.get(log_url, headers=headers, params=params)
    res.raise_for_status()

    log_text = res.text
    print("📜 ABot Execution Log:\n")
    print(log_text)

    # Save to file as well
    with open("abot_log.log", "w") as f:
        f.write(log_text)

def get_summary(folder):
    print("📊 Fetching execution summary...")
    params = {"foldername": folder, "page": 1, "limit": 9998}
    res = requests.get(SUMMARY_URL, headers=headers, params=params)
    res.raise_for_status()
    summary = res.json()
    os.makedirs("results", exist_ok=True)
    with open("results/execution_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    return summary

def generate_reports(summary, tag):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    result = summary["feature_summary"]["result"]
    failed = result["totalScenarios"]["totalScenariosFailed"]["totalScenariosFailedNumber"]
    passed = result["totalScenarios"]["totalScenariosPassed"]["totalScenariosPassedNumber"]
    total = result["totalScenarios"]["totalScenariosNumber"]

    status = "PASS" if failed == 0 else "FAIL"
    exec_user = summary["feature_summary"]["executed_by"]

    safe_tag = tag.replace("@", "").replace(".", "_").replace("-", "_")
    base_name = f"results/{safe_tag}_{timestamp}"

    # Plain text summary
    with open(f"{base_name}_summary.txt", "w") as f:
        f.write(f"Feature Tag: {tag}\n")
        f.write(f"Executed By: {exec_user}\n")
        f.write(f"Total Scenarios: {total}\n")
        f.write(f"Passed: {passed}\n")
        f.write(f"Failed: {failed}\n")
        f.write(f"Status: {status}\n")

    # JSON result
    with open(f"{base_name}_result.json", "w") as f:
        json.dump(summary, f, indent=2)

    # HTML report
    with open(f"{base_name}_report.html", "w") as f:
        f.write(f"""<html><head><title>Test Report - {tag}</title></head>
        <body>
        <h1>Test Report</h1>
        <ul>
            <li><b>Feature Tag:</b> {tag}</li>
            <li><b>Executed By:</b> {exec_user}</li>
            <li><b>Total:</b> {total}</li>
            <li><b>Passed:</b> {passed}</li>
            <li><b>Failed:</b> {failed}</li>
            <li><b>Status:</b> <span style="color:{'green' if status=='PASS' else 'red'}">{status}</span></li>
        </ul>
        <pre>{json.dumps(summary, indent=4)}</pre>
        </body></html>
        """)
    print("📄 Reports generated in /results folder:")
    print(f"- Summary: {base_name}_summary.txt")
    print(f"- JSON:    {base_name}_result.json")
    print(f"- HTML:    {base_name}_report.html")

def check_result(summary):
    result = summary["feature_summary"]["result"]
    failed = result["totalScenarios"]["totalScenariosFailed"]["totalScenariosFailedNumber"]
    if failed > 0:
        print(f"❌ Test failed: {failed} scenario(s) failed.")
        sys.exit(1)
    else:
        print("✅ All test scenarios passed.")

# ----------------- MAIN -----------------
if __name__ == "__main__":
    login()
    update_config()
    execute_feature()
    poll_status()
    
    # Fetch latest artifact name and URL
    folder = get_latest_artifact()        
    download_and_print_log(folder)
    
    summary = get_summary(folder)
    generate_reports(summary, FEATURE_TAG)
    check_result(summary)
