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

# Core VM Configuration
CORE_IP = "10.176.26.58"

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


def create_external_core_config_files():
    """Create configuration files for external core on the filesystem"""
    print("=== Creating External Core Configuration Files ===")
    
    config_commands = [
        # Create custom testbed file with external core IPs
        f"""cat > /tmp/create_testbed.py << 'EOF'
import os
import shutil

# Paths
original_testbed = "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/IOSMCN/testbeds/testbed-5G-IOSMCN.properties"
new_testbed = "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/IOSMCN/testbeds/testbed-5G-IOSMCN-external-core.properties"

# Read original testbed
try:
    with open(original_testbed, 'r') as f:
        content = f.read()
    
    # Replace all 10.42.x.x IPs with external core IP
    import re
    content = re.sub(r'10\.42\.\d+\.\d+', '{CORE_IP}', content)
    
    # Write new testbed file
    with open(new_testbed, 'w') as f:
        f.write(content)
    
    print(f"Created external core testbed: {{new_testbed}}")
    print(f"Replaced IPs with: {CORE_IP}")

except Exception as e:
    print(f"Error creating testbed file: {{e}}")
EOF

python3 /tmp/create_testbed.py""",

        # Create custom SUT variables file
        f"""cat > /tmp/create_sutvars.py << 'EOF'
import os

sut_vars_file = "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/IOSMCN/sut-vars/external-core.properties"

sut_vars_content = '''# External Core SUT Variables
# Core Network Functions
amf.ip={CORE_IP}
amf.port=38412
nrf.ip={CORE_IP}
nrf.port=8080
smf.ip={CORE_IP}
smf.port=29502
upf.ip={CORE_IP}
upf.port=2152
ausf.ip={CORE_IP}
udm.ip={CORE_IP}
udr.ip={CORE_IP}
pcf.ip={CORE_IP}
nssf.ip={CORE_IP}

# Network interfaces
core.network.ip={CORE_IP}
n2.interface.ip={CORE_IP}
n3.interface.ip={CORE_IP}
n4.interface.ip={CORE_IP}

# External core mode
external.core.enabled=true
core.deployment.type=external
'''

try:
    with open(sut_vars_file, 'w') as f:
        f.write(sut_vars_content)
    print(f"Created SUT variables file: {{sut_vars_file}}")
except Exception as e:
    print(f"Error creating SUT variables file: {{e}}")
EOF

python3 /tmp/create_sutvars.py"""
    ]
    
    return config_commands


def execute_core_config_setup():
    """Execute configuration setup on the ABot system"""
    print("=== Setting Up External Core Configuration ===")
    
    import subprocess
    import tempfile
    
    try:
        # Create the configuration scripts
        commands = create_external_core_config_files()
        
        for i, command in enumerate(commands):
            print(f"Executing config setup {i+1}/{len(commands)}...")
            
            # Write command to temporary script
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                f.write('#!/bin/bash\n')
                f.write('set -e\n')
                f.write(command)
                script_path = f.name
            
            # Make executable and run
            os.chmod(script_path, 0o755)
            result = subprocess.run(['bash', script_path], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print(f"✔ Config setup {i+1} completed successfully")
                if result.stdout:
                    print(result.stdout)
            else:
                print(f"⚠ Config setup {i+1} had issues: {result.stderr}")
            
            # Clean up
            os.unlink(script_path)
            
    except Exception as e:
        print(f"❌ Configuration setup failed: {e}")
        # Continue anyway - we'll try API updates
        return False
    
    return True


def update_config_with_core():
    print("=== Configuration Phase with External Core ===")
    
    # First, try to create config files directly
    config_created = execute_core_config_setup()
    
    try:
        # Method 1: Use custom external core files if created
        if config_created:
            payload1 = {
                "update": {
                    "ABOT.SUTVARS.ORAN": "",
                    "ABOT.SUTVARS": "file:IOSMCN/sut-vars/external-core.properties",
                }
            }
            testbed_file = "file:IOSMCN/testbeds/testbed-5G-IOSMCN-external-core.properties"
        else:
            # Method 2: Override existing config with external core IPs
            payload1 = {
                "update": {
                    "ABOT.SUTVARS.ORAN": "",
                    "ABOT.SUTVARS": "file:IOSMCN/sut-vars/default5G.properties",
                    # Override core IPs directly in config
                    "AMF1_IP": CORE_IP,
                    "AUSF1_IP": CORE_IP,
                    "NRF1_IP": CORE_IP,
                    "NSSF1_IP": CORE_IP,
                    "PCF1_IP": CORE_IP,
                    "SMF1_IP": CORE_IP,
                    "UDM1_IP": CORE_IP,
                    "UPF1_IP": CORE_IP,
                    "CORE_NETWORK_IP": CORE_IP,
                }
            }
            testbed_file = "file:IOSMCN/testbeds/testbed-5G-IOSMCN.properties"
        
        params1 = {
            "filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABotConfig.properties"
        }
        res1 = requests.post(CONFIG_URL, headers=headers, json=payload1, params=params1, timeout=30)
        res1.raise_for_status()
        print(f"✔ Updated core IPs to {CORE_IP} → ABotConfig.properties")

        # Step 2: Update testbed configuration
        payload2 = {
            "update": {
                "ABOT.TESTBED": testbed_file,
                "LOAD_SWITCH": "off",
                # Additional overrides for external core
                "SUT_AMF1_IP": CORE_IP,
                "SUT_AUSF1_IP": CORE_IP,
                "SUT_NRF1_IP": CORE_IP,
                "SUT_NSSF1_IP": CORE_IP,
                "SUT_PCF1_IP": CORE_IP,
                "SUT_SMF1_IP": CORE_IP,
                "SUT_UDM1_IP": CORE_IP,
                "SUT_UPF1_IP": CORE_IP,
                "EXTERNAL_CORE_MODE": "true",
            }
        }
        params2 = {
            "filename": "/etc/rebaca-test-suite/config/ajeesh_cazelabs_com/ABot_System_Configs/ABotConfig_Primary_Configuration.properties"
        }
        res2 = requests.post(CONFIG_URL, headers=headers, json=payload2, params=params2, timeout=30)
        res2.raise_for_status()
        print("✔ Updated testbed with external core → ABot_Primary_Configuration.properties")

        time.sleep(10)  # Extra time for config to take effect
        
    except Exception as e:
        print(f"❌ Config update failed: {e}")
        sys.exit(1)


def verify_core_connectivity():
    print("=== Verifying Core Connectivity ===")
    import socket
    
    # Test basic connectivity to core VM
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((CORE_IP, 22))  # Test SSH port first
        sock.close()
        
        if result == 0:
            print(f"✔ Core VM {CORE_IP} is reachable")
        else:
            print(f"❌ Core VM {CORE_IP} is not reachable")
            return False
            
        # Test core service ports
        core_ports = [8080, 80, 38412, 2152]
        for port in core_ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((CORE_IP, port))
            sock.close()
            
            if result == 0:
                print(f"✔ Core service on port {port} is accessible")
            else:
                print(f"⚠ Core service on port {port} is not accessible")
        
        return True
    except Exception as e:
        print(f"❌ Connectivity check failed: {e}")
        return False


def wait_for_system_ready():
    print("Waiting for system to be ready after config...")
    time.sleep(15)  # Extended wait time for core integration


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
    max_attempts = 240  # Extended timeout for core integration tests
    for attempt in range(max_attempts):
        try:
            res = requests.get(f"{STATUS_URL}/{exec_id}", headers=headers, timeout=30)
            res.raise_for_status()
            json_data = res.json()
            print(f"Status check #{attempt + 1}")
            
            # Enhanced logging for core integration debugging
            if attempt % 10 == 0:  # Print full status every 10th check
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
            passed = 0
            total = len(summary["data"])
            
            for item in summary["data"]:
                status = item.get("Status", "").lower()
                if status == "fail":
                    failed = True
                elif status == "pass":
                    passed += 1
                    
            print(f"📊 Test Results: {passed}/{total} passed")
            
            if failed:
                with open("test_failed.txt", "w") as f:
                    f.write(f"Tests failed: {total-passed}/{total}\n")
                print("❌ Some tests failed")
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
                feature_name = item.get("FeatureFileName", "Unknown")
                error_msg = item.get("ErrorMessage", "N/A")
                print(f"❌ Failed: {feature_name}")
                print(f"   Error: {error_msg}")
                
                # Check for core connectivity issues
                if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                    print("   💡 This might be a core connectivity issue")


if __name__ == "__main__":
    try:
        print("=== ABot Test Automation with Core Integration Started ===")
        print(f"Using Core VM: {CORE_IP}")
        
        # Login
        login()
        
        # Verify core connectivity before proceeding
        if not verify_core_connectivity():
            print("❌ Core connectivity check failed. Please verify core VM is accessible.")
            sys.exit(1)
        
        # Update configuration with core integration
        update_config_with_core()
        
        # Wait for system to be ready
        wait_for_system_ready()
        
        # Execute the test
        exec_id = execute_feature()
        poll_status(exec_id)
        
        # Get results
        folder = get_artifact_folder()
        summary = get_summary(folder)
        test_passed = check_result(summary)
        
        if not test_passed:
            analyze_execution_failure(summary)

        # Save artifact folder for GitHub Actions
        with open("artifact_path.txt", "w") as f:
            f.write(folder)

        print("=== ABot Test Automation with Core Integration Completed ===")
        sys.exit(0 if test_passed else 1)

    except KeyboardInterrupt:
        print("❌ Interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
