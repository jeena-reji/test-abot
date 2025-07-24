import requests

ABOT_URL = "http://10.176.27.73/abotrest/abot/api/v5"
EMAIL = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"

session = requests.Session()

def log(msg): print(msg)

def login():
    log("🔐 Logging in...")
    r = session.post(f"{ABOT_URL}/login", json={"email": EMAIL, "password": PASSWORD})
    token = r.json().get("data", {}).get("token")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})
        log("✅ Logged in.")
    else:
        log("❌ Login failed.")
        exit(1)

def list_path(path):
    log(f"\n📂 Listing path: {path}")
    r = session.get(f"{ABOT_URL}/folder/list", params={"path": path})
    log(f"🔎 Status: {r.status_code}")
    log(f"📨 Raw: {r.text}")
    return r


def main():
    login()
    list_path("featureFiles")             # root folder
    list_path("featureFiles/IMS")         # known subfolder

if __name__ == "__main__":
    main()
