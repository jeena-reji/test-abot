import requests
import sys

ABOT_URL = "http://10.176.27.73/abotrest"
LOGIN_URL = f"{ABOT_URL}/abot/api/v5/login"
TAGS_URL = f"{ABOT_URL}/abot/api/v5/get_all_tags"

USERNAME = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"

def login():
    payload = {
        "userId": USERNAME,
        "password": PASSWORD
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(LOGIN_URL, json=payload, headers=headers)
        response.raise_for_status()
        token = response.json().get("token")
        if not token:
            print("Failed to get token from login response.")
            sys.exit(1)
        return token
    except requests.exceptions.RequestException as e:
        print(f"Login failed: {e}")
        sys.exit(1)

def list_tags(token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(TAGS_URL, headers=headers)
        response.raise_for_status()
        tags = response.json()
        print("Available Tags:")
        for tag in tags:
            print(f"- {tag}")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching tags: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] != "--list-tags":
        print("Usage: python abot_runner.py --list-tags")
        sys.exit(1)

    token = login()
    list_tags(token)
