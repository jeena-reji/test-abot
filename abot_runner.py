import requests
import sys

# --- ABot API URLs ---
ABOT_URL = "http://10.176.27.73/abotrest"
LOGIN_URL = f"{ABOT_URL}/abot/api/v5/login"
TAGS_URL = f"{ABOT_URL}/abot/api/v5/feature_files/tags"

# --- Credentials ---
USERNAME = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"

# --- Login and get token ---
def login():
    payload = {
        "username": USERNAME,
        "password": PASSWORD
    }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(LOGIN_URL, json=payload, headers=headers)
        response.raise_for_status()
        token = response.json().get("token")
        if not token:
            print("Login successful but no token returned.")
            sys.exit(1)
        return token
    except requests.exceptions.RequestException as e:
        print(f"Login request failed: {e}")
        sys.exit(1)

# --- List available tags ---
def list_tags(token):
    headers = {
        "Authorization": f"Bearer {token}"
    }
    try:
        response = requests.get(TAGS_URL, headers=headers)
        response.raise_for_status()
        tags = response.json()
        print("Available tags:")
        for tag in tags:
            print(f"- {tag}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to get tags: {e}")
        sys.exit(1)

# --- Main ---
if __name__ == "__main__":
    if "--list-tags" in sys.argv:
        token = login()
        list_tags(token)
    else:
        print("Usage: python abot_runner.py --list-tags")
