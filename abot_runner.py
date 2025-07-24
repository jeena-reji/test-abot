import requests
import os

# ABot Configuration
ABOT_URL = "http://10.176.27.73/abotrest/abot/api/v5"
EMAIL = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"

session = requests.Session()

def log(msg): print(msg)

def login():
    log("\n🔐 Logging in to ABot...")
    resp = session.post(f"{ABOT_URL}/login", json={"email": EMAIL, "password": PASSWORD})
    log(f"🔎 Status: {resp.status_code}")
    try:
        data = resp.json().get("data", {})
        token = data.get("token")
        if token:
            session.headers.update({"Authorization": f"Bearer {token}"})
            log("✅ Logged in successfully.")
        else:
            log("❌ Login failed, token missing.")
            exit(1)
    except Exception as e:
        log(f"❌ Login failed: {e}")
        exit(1)

def list_folder(path, indent=0):
    try:
        log(f"📂 Listing: '{path}'")
        resp = session.get(f"{ABOT_URL}/files", params={"path": path, "include_file": "true"})
        log(f"🔎 Status: {resp.status_code}")
        log(f"📨 Raw response: {resp.text}")  # <-- Add this line

        if resp.status_code != 200:
            log("❌ Error listing: " + path + " → " + resp.text)
            return

        items = resp.json().get("data", [])
        prefix = " " * indent
        for item in items:
            name = item.get("name", "UNKNOWN")
            full_path = os.path.join(path, name).replace("\\", "/")
            if item.get("is_file"):
                print(f"{prefix}📄 {name}")
            else:
                print(f"{prefix}📁 {name}/")
                list_folder(full_path, indent + 4)
    except Exception as e:
        log(f"⚠️ Failed to list {path}: {e}")

def main():
    login()
    log("\n📂 Listing all contents from ABot root `/` path...\n")
    list_folder("")  # Root path
    log("\n✅ Done listing all ABot folders and files.\n")

if __name__ == "__main__":
    main()
