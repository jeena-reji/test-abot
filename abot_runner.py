import requests, time, sys, json, os

ABOT_URL = "http://10.176.27.73/abotrest"
LOGIN_URL = f"{ABOT_URL}/abot/api/v5/login"
CONFIG_URL = f"{ABOT_URL}/abot/api/v5/update_config_properties"
EXECUTE_URL = f"{ABOT_URL}/abot/api/v5/feature_files/execute"
STATUS_URL = f"{ABOT_URL}/abot/api/v5/execution_status"
ARTIFACT_URL = f"{ABOT_URL}/abot/api/v5/latest_artifact_name"
SUMMARY_URL = f"{ABOT_URL}/abot/api/v5/artifacts/execFeatureSummary"
VERIFY_CONFIG_URL = f"{ABOT_URL}/abot/api/v5/config_properties"  # Add this to verify config

USERNAME = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"
FEATURE_TAG = "5gs-initial-registration-sdcore-0.0.10"

CONFIG_FILE = "/etc/rebaca-test-suite/config/admin/ABotConfig.properties"

headers = {"Content-Type": "application/json"}

def login():
    print("Logging in...")
    payload = {"email": USERNAME, "password": PASSWORD, "expires": False}
    try:
        res = requests.post(LOGIN_URL, json=payload, timeout=30)
        res.raise_for_status()
        token = res.json()["data"]["token"]
        headers["Authorization"] = f"Bearer {token}"
        print("Login successful.")
        return token
    except requests.exceptions.RequestException as e:
        print(f"Login failed: {e}")
        sys.exit(1)

def verify_current_config():
    """Verify current configuration before updating"""
    print("Verifying current configuration...")
    try:
        params = {"filename": CONFIG_FILE}
        res = requests.get(VERIFY_CONFIG_URL, headers=headers, params=params, timeout=30)
        res.raise_for_status()
        config_data = res.json()
        
        print("Current configuration:")
        print(json.dumps(config_data, indent=2))
        
        # Check if ABOT.TESTBED exists and its current value
        if "data" in config_data and "properties" in config_data["data"]:
            properties = config_data["data"]["properties"]
            current_testbed = properties.get("ABOT.TESTBED", "NOT_SET")
            print(f"Current ABOT.TESTBED: {current_testbed}")
            return current_testbed
        else:
            print("Could not find configuration properties")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Config verification endpoint not available: {e}")
        print("Proceeding without config verification...")
        return None

def update_config():
    print("Updating config...")
    
    # First verify current config
    current_testbed = verify_current_config()
    
    # Update configuration with explicit testbed
    payload = {
        "update": {
            "ABOT.TESTBED": "testbed-5G-IOSMCN"
        }
    }
    
    try:
        params = {"filename": CONFIG_FILE}
        res = requests.post(CONFIG_URL, headers=headers, json=payload, params=params, timeout=30)
        res.raise_for_status()
        print(f"Config update response: {res.status_code}")
        print(f"Config updated: ABOT.TESTBED = {payload['update']['ABOT.TESTBED']}")
        
        # Wait a moment for config to propagate
        time.sleep(5)
        
        # Verify the update was successful
        verify_current_config()
        
    except requests.exceptions.RequestException as e:
        print(f"Config update failed: {e}")
        sys.exit(1)

def wait_for_system_ready():
    """Wait for system to be ready after config update"""
    print("Waiting for system to be ready...")
    time.sleep(10)  # Give more time for config to propagate

def execute_feature():
    print(f"Executing feature tag: {FEATURE_TAG}")
    payload = {"params": FEATURE_TAG}
    
    try:
        res = requests.post(EXECUTE_URL, headers=headers, json=payload, timeout=30)
        res.raise_for_status()
        print("Test execution started successfully.")
        print(f"Execution response: {res.status_code}")
        
        # Print response for debugging
        if res.text:
            try:
                response_data = res.json()
                print("Execution response data:")
                print(json.dumps(response_data, indent=2))
            except json.JSONDecodeError:
                print(f"Raw execution response: {res.text}")
                
    except requests.exceptions.RequestException as e:
        print(f"Test execution failed: {e}")
        sys.exit(1)

def poll_status():
    print("Polling execution status...")
    max_attempts = 180  # 30 minutes maximum wait time
    attempt = 0
    
    while attempt < max_attempts:
        try:
            res = requests.get(STATUS_URL, headers=headers, timeout=30)
            res.raise_for_status()
            json_data = res.json()
            
            print(f"Status check #{attempt + 1}")
            print("Raw /execution_status response:")
            print(json.dumps(json_data, indent=2))

            # Check for execution completion
            if "executing" in json_data and "executing" in json_data["executing"]:
                exec_list = json_data["executing"]["executing"]
                if exec_list:
                    is_executing = exec_list[0].get("is_executing", False)
                    if not is_executing:
                        print("Execution completed.")
                        return
                    else:
                        print("Still running... waiting 10s")
                else:
                    print("No execution found in list. Execution may have completed.")
                    return
            else:
                print("Unexpected execution_status structure. Execution may have completed.")
                return
            
        except requests.exceptions.RequestException as e:
            print(f"Status check failed: {e}")
            
        time.sleep(10)
        attempt += 1
    
    print("Maximum wait time reached. Proceeding to check results.")

def get_artifact_folder():
    try:
        res = requests.get(ARTIFACT_URL, headers=headers, timeout=30)
        res.raise_for_status()
        folder = res.json()["data"]["latest_artifact_timestamp"]
        print(f"Latest artifact folder: {folder}")
        return folder
    except requests.exceptions.RequestException as e:
        print(f"Failed to get artifact folder: {e}")
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
        
        print("Execution Summary:")
        print(json.dumps(summary, indent=2))
        return summary
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to get summary: {e}")
        sys.exit(1)

def check_result(summary):
    try:
        result = summary["feature_summary"]["result"]
        
        # Fix: Use the correct key names from the actual response
        failed = result["totalScenarios"]["totalScenariosFailed"]["totalScenariosFailedNumber"]
        passed = result["totalScenarios"]["totalScenariosPassed"]["totalScenariosPassedNumber"]
        total = result["totalScenarios"]["totalScenariosTotal"]["totalScenariosTotalNumber"]
        
        print(f"Test Results: {passed} passed, {failed} failed, {total} total")
        
        # Detailed step results
        steps = result["totalSteps"]
        steps_passed = steps["totalStepsPassed"]["totalStepsPassedNumber"]
        steps_failed = steps["totalStepsFailed"]["totalStepsFailedNumber"]
        steps_skipped = steps["totalStepsSkipped"]["totalStepsSkippedNumber"]
        
        print(f"Step Results: {steps_passed} passed, {steps_failed} failed, {steps_skipped} skipped")
        
        if failed > 0:
            print(f"\n❌ Test FAILED: {failed} scenario(s) failed.")
            
            # Show detailed failure information
            print("\nFailure Details:")
            for i, data in enumerate(result.get("data", []), 1):
                scenario_name = data.get("scenarioName", "Unknown Scenario")
                feature_name = data.get("featureName", "Unknown Feature")
                scenario_failed = data["scenario"]["failed"]
                steps_failed = data["steps"]["failed"]
                
                if scenario_failed > 0:
                    print(f"  {i}. Feature: {feature_name}")
                    print(f"     Scenario: {scenario_name}")
                    print(f"     Failed Steps: {steps_failed}")
            
            with open("test_failed.txt", "w") as f:
                f.write(str(failed))
                
            return False
        else:
            print("✅ All test scenarios passed.")
            return True
            
    except KeyError as e:
        print(f"Error parsing results: {e}")
        print("Full summary structure:")
        print(json.dumps(summary, indent=2))
        return False

def download_and_print_log(folder):
    """Try multiple log endpoints to get execution logs"""
    log_endpoints = [
        f"{ABOT_URL}/abot/api/v5/artifacts/logs",
        f"{ABOT_URL}/abot/api/v5/artifacts/log",
        f"{ABOT_URL}/abot/api/v5/execution_logs",
    ]
    
    params = {"foldername": folder}
    
    for i, log_url in enumerate(log_endpoints, 1):
        print(f"Trying log endpoint {i}/{len(log_endpoints)}: {log_url}")
        try:
            res = requests.get(log_url, headers=headers, params=params, timeout=60)
            res.raise_for_status()

            log_text = res.text
            if log_text and log_text.strip():
                print("✅ ABot Execution Log Found:\n")
                print(log_text)

                # Save to file as well
                with open("abot_log.log", "w") as f:
                    f.write(log_text)
                return
            else:
                print(f"Empty response from endpoint {i}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Endpoint {i} failed: {e}")
            continue
    
    print("⚠️  Could not retrieve execution logs from any endpoint")
    print("You may need to check logs manually in the ABot UI or try a different API endpoint")
    
    # Create a summary log file with available information
    with open("execution_info.log", "w") as f:
        f.write(f"Artifact Folder: {folder}\n")
        f.write(f"Execution completed but logs not accessible via API\n")
        f.write(f"Check ABot UI at: https://10.176.27.73/abotfrontail_9004\n")

def analyze_execution_failure(summary):
    """Analyze why the test failed based on the execution summary"""
    print("\n=== FAILURE ANALYSIS ===")
    
    result = summary["feature_summary"]["result"]
    
    # Check for common failure patterns
    print("1. Checking execution status...")
    
    for i, data in enumerate(result.get("data", []), 1):
        feature_name = data.get("featureName", "Unknown")
        scenario_name = data.get("scenarioName", "Unknown")
        
        print(f"\nTest Run #{i}:")
        print(f"  Feature: {feature_name}")
        print(f"  Scenario: {scenario_name}")
        
        # Step analysis
        steps = data["steps"]
        print(f"  Steps - Passed: {steps['passed']}, Failed: {steps['failed']}, Skipped: {steps['skipped']}")
        
        # Feature status
        feature_status = data["features"]
        print(f"  Duration: {feature_status['duration']:.2f}s")
        print(f"  Status: {feature_status['status']}")
        
        # Check for testbed issues
        if steps['failed'] > 0 and steps['skipped'] > steps['passed']:
            print("  ⚠️  HIGH SKIP RATE - Possible testbed configuration issue")
        
        if feature_status['duration'] < 10:
            print("  ⚠️  SHORT EXECUTION TIME - Possible early failure")
    
    # Configuration recommendations
    print("\n2. Possible Issues:")
    print("   - Testbed configuration may not be properly set")
    print("   - 5G core network components (AMF/SMF/UPF) may not be running")
    print("   - Network connectivity issues between test components")
    print("   - Authentication/security configuration mismatch")
    
    print("\n3. Recommended Actions:")
    print("   - Verify testbed is running: testbed-5G-IOSMCN-emu-amf-sut-smf")
    print("   - Check ABot UI configuration matches script settings")
    print("   - Ensure 5G core network is properly deployed and accessible")
    print("   - Review detailed logs in ABot UI for specific error messages")

if __name__ == "__main__":
    try:
        print("=== ABot Test Automation Started ===")
        login()
        
        print("\n=== Configuration Phase ===")
        update_config()
        wait_for_system_ready()
        
        print("\n=== Execution Phase ===")
        execute_feature()
        poll_status()
        
        print("\n=== Results Phase ===")
        folder = get_artifact_folder()
        summary = get_summary(folder)
        test_passed = check_result(summary)
        
        if not test_passed:
            analyze_execution_failure(summary)
        
        download_and_print_log(folder)

        # Save folder path for GitHub Actions
        with open("artifact_path.txt", "w") as f:
            f.write(folder)
            
        print("=== ABot Test Automation Completed ===")
        
        if not test_passed:
            print("❌ TESTS FAILED - Check the failure analysis above")
            print("Exiting with failure code for CI/CD pipeline...")
            sys.exit(1)
        else:
            print("✅ ALL TESTS PASSED")
            sys.exit(0)
        
    except KeyboardInterrupt:
        print("\nExecution interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
