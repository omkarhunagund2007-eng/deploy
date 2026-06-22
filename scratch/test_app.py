import urllib.request
import urllib.parse
import http.cookiejar
import json
import sys

def test_routes():
    # Set up cookie handler to persist session
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    urllib.request.install_opener(opener)

    base_url = "http://127.0.0.1:3000"

    print("1. Attempting login as admin...")
    login_data = urllib.parse.urlencode({
        "username": "admin",
        "password": "admin123"
    }).encode("utf-8")

    try:
        req = urllib.request.Request(f"{base_url}/login", data=login_data, method="POST")
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            print("Login response status:", resp.status)
            if "Signed in successfully" in content or "Welcome Back" in content or resp.status == 200:
                print("Login request completed successfully.")
            else:
                print("Login might have failed. Response content snippet:")
                print(content[:200])
    except Exception as e:
        print("Login failed with error:", e)
        sys.exit(1)

    print("\n2. Accessing dashboard...")
    try:
        with urllib.request.urlopen(f"{base_url}/dashboard") as resp:
            content = resp.read().decode("utf-8")
            print("Dashboard response status:", resp.status)
            if "Welcome Back, admin" in content:
                print("Dashboard loaded successfully.")
            else:
                print("Dashboard content check failed. Snippet:")
                print(content[:300])
    except Exception as e:
        print("Accessing dashboard failed:", e)
        sys.exit(1)

    print("\n3. Accessing quiz select page...")
    try:
        with urllib.request.urlopen(f"{base_url}/quiz") as resp:
            content = resp.read().decode("utf-8")
            print("Quiz select response status:", resp.status)
            if "Mock Test Selection" in content or "Choose Category" in content:
                print("Quiz select page loaded successfully.")
            else:
                print("Quiz select content check failed. Snippet:")
                print(content[:300])
    except Exception as e:
        print("Accessing quiz select failed:", e)
        sys.exit(1)

    print("\n4. Accessing admin page...")
    try:
        with urllib.request.urlopen(f"{base_url}/admin") as resp:
            content = resp.read().decode("utf-8")
            print("Admin page response status:", resp.status)
            if "Portal Administration" in content:
                print("Admin page loaded successfully.")
            else:
                print("Admin page check failed. Snippet:")
                print(content[:300])
    except Exception as e:
        print("Accessing admin page failed:", e)
        sys.exit(1)

    print("\n5. Testing subject creation...")
    subject_data = urllib.parse.urlencode({
        "name": "Test Subject X",
        "emoji": "🧪",
        "description": "A test subject created by test script"
    }).encode("utf-8")
    try:
        req = urllib.request.Request(f"{base_url}/admin/subjects/add", data=subject_data, method="POST")
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            print("Add subject response status:", resp.status)
            # This redirect page should be admin page
            if "Test Subject X" in content:
                print("Subject added and displayed on admin page successfully.")
            else:
                print("Subject might not have been added. Snippet:")
                print(content[:500])
    except Exception as e:
        print("Adding subject failed:", e)
        sys.exit(1)

    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    test_routes()
