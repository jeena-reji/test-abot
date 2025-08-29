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
    execution_completed = False
    
    while True:
        res = requests.get(STATUS_URL, headers=headers, timeout=30)
        res.raise_for_status()
        exec_info = res.json().get("executing", {})

        executing_list = exec_info.get("executing", [])
        statuses = exec_info.get("execution_status", [])

        # Filter for this FEATURE_TAG and show all execution status
        filtered_execs = [e for e in executing_list if FEATURE_TAG in e.get("name", "")]
        
        # Show all execution statuses (not just filtered ones)
        print("Execution status for current tag:")
        if filtered_execs:
            print(json.dumps(filtered_execs, indent=2))
        else:
            print("[]")
        print(json.dumps(statuses, indent=2))

        # Check if execution is completed
        if any(s["name"] == "execution completed" and s["status"] == 1 for s in statuses):
            if not execution_completed:
                print("✔ ABot reports execution completed.")
                execution_completed = True
                # Wait a bit more for artifacts to be ready after execution completes
                print("Waiting for artifacts to be generated...")
                time.sleep(15)
                break

        print("Still running in ABot... waiting 10s")
        time.sleep(10)


def get_artifact_folder():
    print("Fetching artifact folder...")
    
    # Try multiple approaches to find the artifact
    for attempt in range(30):  # Increased attempts
        try:
            # Method 1: Try latest artifact endpoint
            try:
                res = requests.get(LATEST_ARTIFACT_URL, headers=headers, timeout=30)
                if res.status_code == 200:
                    latest_data = res.json()
                    if latest_data.get("data"):
                        latest_folder = latest_data["data"]
                        # Debug: Print what we got
                        if attempt == 0:
                            print(f"Debug: Latest artifact from API: '{latest_folder}'")
                        
                        # Check for exact match first
                        if FEATURE_TAG in latest_folder:
                            print(f"✔ Latest artifact folder: {latest_folder}")
                            return latest_folder
                        # Check for close match
                        elif ("5gs-initial-registration" in latest_folder and 
                              ("with-integrity-and-ciphering" in latest_folder or "sdcore" in latest_folder)):
                            print(f"⚠ Latest folder '{latest_folder}' does not exactly contain tag '{FEATURE_TAG}', using it anyway.")
                            print(f"✔ Latest artifact folder: {latest_folder}")
                            return latest_folder
                        elif attempt == 0:
                            print(f"Debug: Latest folder doesn't match our pattern: '{latest_folder}'")
            except Exception as e:
                if attempt == 0:
                    print(f"⚠ Latest artifact endpoint failed: {e}")

            # Method 2: List all artifacts and find matches
            res = requests.get(ARTIFACT_URL, headers=headers, timeout=30)
            res.raise_for_status()
            response_data = res.json()
            all_data = response_data.get("data", [])
            
            # Debug: Print raw response structure on first attempt
            if attempt == 0:
                print(f"Debug: Artifacts API response keys: {list(response_data.keys())}")
                print(f"Debug: Found {len(all_data)} total artifacts in 'data' field")
                
                # Show some sample artifacts to understand structure
                sample_count = min(3, len(all_data))
                for i, item in enumerate(all_data[-sample_count:]):
                    print(f"Debug: Sample artifact {i+1}: {item}")

            matching = []
            for item in all_data:
                label = ""
                if isinstance(item, dict):
                    label = item.get("label", "")
                elif isinstance(item, str):
                    label = item
                    item = {"label": label, "epoch_time": 0}
                
                # Look for artifacts that match our feature (be more aggressive in matching)
                if (FEATURE_TAG in label or 
                    ("5gs-initial-registration" in label and "with-integrity-and-ciphering" in label) or
                    ("5gs-initial-registration" in label and "sdcore" in label)):
                    matching.append(item)
                    if attempt == 0:
                        print(f"Debug: Found matching artifact: {label}")

            if matching:
                # Sort by epoch_time and get the most recent
                folder_item = sorted(matching, key=lambda x: x.get("epoch_time", 0))[-1]
                folder_name = folder_item.get("label", folder_item) if isinstance(folder_item, dict) else folder_item
                
                if FEATURE_TAG not in folder_name:
                    print(f"⚠ Found folder '{folder_name}' does not exactly contain tag '{FEATURE_TAG}', using it anyway.")
                
                print(f"✔ Latest artifact folder: {folder_name}")
                return folder_name

            print(f"⚠ No artifact yet for tag {FEATURE_TAG}, retrying... (attempt {attempt+1}/30)")
            time.sleep(10)
            
        except Exception as e:
            print(f"⚠ Error fetching artifacts (attempt {attempt+1}): {e}")
            time.sleep(10)

    print("❌ Could not find matching artifact folder for this tag.")
    # Don't exit - let the workflow continue to see if we can get more info
    return None


def download_artifact(folder: str):
    if not folder:
        print("❌ No artifact folder provided, cannot download.")
        return
    print(f"Downloading artifact for folder: {folder}")
    try:
        params = {"path": folder}
        res = requests.get(ARTIFACT_DOWNLOAD_URL, headers=headers, params=params, timeout=120, stream=True)
        res.raise_for_status()
        out_file = "artifact.zip"
        with open(out_file, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        print(f"✔ Artifact downloaded and saved as {out_file}")
    except Exception as e:
        print(f"⚠ Failed to download artifact: {e}")


def get_summary(folder: str):
    if not folder:
        print("❌ No artifact folder available, cannot fetch summary.")
        return {}
    print("Fetching execution summary...")
    try:
        params = {"foldername": folder, "page": 1, "limit": 9998}
        res = requests.get(SUMMARY_URL, headers=headers, params=params, timeout=60)
        res.raise_for_status()
        summary = res.json()
        with open("execution_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        print(json.dumps(summary, indent=2))
        return summary
    except Exception as e:
        print(f"⚠ Failed to get summary: {e}")
        return {}


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


def print_failure_analysis(summary: dict):
    """Print detailed failure analysis"""
    print("=== Failure Analysis ===")
    try:
        features = summary.get("feature_summary", {}).get("result", {}).get("data", [])
        total_steps = summary.get("feature_summary", {}).get("result", {}).get("totalSteps", {})
        
        if features:
            for f in features:
                feature_name = f.get("featureName", "Unknown")
                scenario_name = f.get("scenarioName", "Unknown scenario")
                steps = f.get("steps", {})
                feature_status = f.get("features", {}).get("status", "unknown")
                duration = f.get("features", {}).get("duration", 0)
                
                print(f"\nFeature: {feature_name}")
                print(f"Scenario: {scenario_name}")
                print(f"Status: {feature_status}")
                print(f"Duration: {duration:.2f} seconds")
                print(f"Steps - Passed: {steps.get('passed', 0)}, Failed: {steps.get('failed', 0)}, Skipped: {steps.get('skipped', 0)}")
                
                if f.get("passed_with_Error", False):
                    print("⚠ Feature passed but with errors")
        
        # Print overall statistics
        if total_steps:
            passed_pct = total_steps.get("totalStepsPassed", {}).get("totalStepsPassedPercentage", 0)
            failed_pct = total_steps.get("totalStepsFailed", {}).get("totalStepsFailedPercentage", 0) 
            skipped_pct = total_steps.get("totalStepsSkipped", {}).get("totalStepsSkippedPercentage", 0)
            
            print(f"\nOverall Results:")
            print(f"Passed: {passed_pct:.1f}%, Failed: {failed_pct:.1f}%, Skipped: {skipped_pct:.1f}%")
            
    except Exception as e:
        print(f"⚠ Error in failure analysis: {e}")


def print_logs_info(folder: str):
    """Print logs information like in the expected output"""
    if folder:
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
        if folder:
            download_artifact(folder)
            summary = get_summary(folder)
            test_passed = check_result(summary)
            
            # Add failure analysis if tests failed
            if not test_passed:
                print_failure_analysis(summary)
            
            print_logs_info(folder)
            
            # save artifact path for GitHub Actions
            with open("artifact_path.txt", "w") as f:
                f.write(str(folder))
        else:
            print("❌ No artifact folder found, cannot proceed with summary and downloads.")
            test_passed = False

        print("=== ABot Test Automation Completed ===")
        sys.exit(0 if test_passed else 1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
