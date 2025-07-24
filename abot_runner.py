import requests
import sys

ABOT_URL = "http://10.176.27.73/abotrest"
LOGIN_URL = f"{ABOT_URL}/abot/api/v5/login"
LIST_TAGS_URL = f"{ABOT_URL}/abot/api/v5/list_tags"

USERNAME = "ajeesh@cazelabs.com"
PASSWORD = "ajeesh1234"

def login():
    try:
        response = requests.post(LOGIN_URL, json={"username": USERNAME, "password": PASSWORD})
        response.raise_for_status()
        token = response.json().get("token")
        if not token:
            print("Login failed: No token received")
            sys.exit(1)
        return token
    except requests.exceptions.RequestException as e:
        print(f"Login request failed: {e}")
        sys.exit(1)

def list_tags(token):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(LIST_TAGS_URL, headers=headers)
        response.raise_for_status()
        tags = response.json().get("tags", [])
        print("Available Tags:")
        for tag in tags:
            print(f"- {tag}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch tags: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--list-tags":
        token = login()
        list_tags(token)
    else:
        print("Usage: python abot_runner.py --list-tags")
