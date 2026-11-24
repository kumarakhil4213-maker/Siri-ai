import json
import urllib.request

CURRENT_VERSION = "1.0.0"
VERSION_URL = "https://raw.githubusercontent.com/kumarakhil4213-maker/Siri-ai/main/version.json"

def check_update():
    try:
        request = urllib.request.Request(
            VERSION_URL,
            headers={"User-Agent": "SIRI-Update-Checker"}
        )

        with urllib.request.urlopen(request, timeout=15) as response:
            latest = json.loads(response.read().decode("utf-8"))

        latest_version = latest.get("version")

        if not latest_version:
            print("GitHub version information is invalid.")
            return

        print("Installed SIRI:", CURRENT_VERSION)
        print("GitHub SIRI:", latest_version)

        if latest_version == CURRENT_VERSION:
            print("SIRI is already up to date.")
        else:
            print("A different version is available.")
            print("Automatic installation is not enabled yet.")

    except Exception as error:
        print("Update check failed:", error)

if __name__ == "__main__":
    check_update()
