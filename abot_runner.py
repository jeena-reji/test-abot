
import requests
import time
import json
import sys
from datetime import datetime

# ========== CONFIG ==========

ABOT_BASE_URL = "http://10.176.27.73/abotrest/abot/api/v5"
USERNAME = "admin"
PASSWORD = "admin1234"
CONFIG_FILENAME = "abot-emulated - testbed-4g5g.properties"
POLL_INTERVAL = 10  # seconds

# ========== AUTH ==========

def login():
    resp = requests.post(f"{ABOT_BASE_URL}/login", json={
        "username": USERNAME,
        "password": PASSWORD
    })
    resp.raise_for_status()
    token = resp.json().get("data", {}).get("token")
    if not token:
        raise Exception("Login failed: No token in response")
    return token

# ========== HEADERS ==========

def auth_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

# ========== FEATURE TAGS ==========

def fetch_feature_tags(token):
    resp = requests.get(f"{ABOT_BASE_URL}/feature_files_tags", headers=auth_headers(token))
    resp.raise_for_status()
    return resp.json().get("data", [])

# ========== CONFIG UPDATE ==========

def update_config(token):
    url = f"{ABOT_BASE_URL}/update_config_properties"
    params = {
        "filename": "/etc/rebaca-test-suite/config/admin/ABotConfig.properties"
    }
    data = {
        "ABotConfig": {
            "TESTBED": CONFIG_FILENAME
        }
    }
    resp = requests.post(url, params=params, headers=auth_headers(token), json=data)
    resp.raise_for_status()
    print("✅ Config updated")

# ========== EXECUTE FEATURE TAG ==========

def execute_tag(token, tag):
    print(f"🚀 Executing feature tag: {tag}")
    resp = requests.post(f"{ABOT_BASE_URL}/feature_files/execute", headers=auth_headers(token), json={
        "feature_tag": tag
    })
    resp.raise_for_status()
    return True

# ========== WAIT FOR EXECUTION ==========

def wait_for_completion(token):
    print("⏳ Waiting for execution to complete...")
    while True:
        resp = requests.get(f"{ABOT_BASE_URL}/execution_status", headers=auth_headers(token))
        resp.raise_for_status()
        status = resp.json().get("data", {}).get("execution_status", "")
        print(f"   → Current status: {status}")
        if status == "COMPLETED":
            return True
        elif status == "FAILED":
            print("❌ Execution failed")
            return False
        time.sleep(POLL_INTERVAL)

# ========== FETCH SUMMARY ==========

def fetch_summary(token):
    resp = requests.get(f"{ABOT_BASE_URL}/execution_summary", headers=auth_headers(token))
    resp.raise_for_status()
    return resp.json()

# ========== MAIN RUNNER ==========

def main():
    token = login()
    update_config(token)
    tags = fetch_feature_tags(token)

    all_results = []
    any_failures = False

    for tag in tags:
        try:
            execute_tag(token, tag)
            completed = wait_for_completion(token)
            if not completed:
                any_failures = True
                all_results.append({
                    "tag": tag,
                    "status": "Execution Failed"
                })
                continue

            summary = fetch_summary(token)
            result = {
                "tag": tag,
                "summary": summary
            }

            if "fail" in json.dumps(summary).lower():
                result["status"] = "Failed"
                any_failures = True
            else:
                result["status"] = "Passed"

            all_results.append(result)

        except Exception as e:
            print(f"❌ Error while executing tag {tag}: {e}")
            any_failures = True
            all_results.append({
                "tag": tag,
                "status": "Error",
                "error": str(e)
            })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"abot_execution_summary_{timestamp}.json", "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"✅ Execution completed for {len(tags)} feature tags")
    if any_failures:
        print("❌ Some executions failed. Failing pipeline.")
        sys.exit(1)

if __name__ == "__main__":
    main()
