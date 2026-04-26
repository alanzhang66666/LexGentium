import requests
import json
import sys

def test_api():
    # Load submission config
    try:
        with open("submission.json", "r", encoding="utf-8-sig") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Error: submission.json not found.")
        return

    url = config.get("api_key")
    headers = config.get("headers", {})
    
    if not url:
        print("Error: api_key (URL) not found in submission.json")
        return

    print(f"Testing API at: {url}")

    # Test Data
    test_cases = [
        {
            "name": "CD Scenario (Plaintiff Lawyer)",
            "payload": {
                "scenario": "CD",
                "case_id": "test_cd_001",
                "dialog_history": [
                    {"turn": 0, "role": "Client", "message": "您好，我想要起草起诉状。"}
                ]
            }
        },
        {
            "name": "DD Scenario (Defendant Lawyer)",
            "payload": {
                "scenario": "DD",
                "case_id": "test_dd_001",
                "dialog_history": [
                    {"turn": 0, "role": "Client", "message": "我收到法院传票了，我是被告，要写答辩状。"}
                ]
            }
        },
        {
            "name": "CI Scenario (Judge)",
            "payload": {
                "scenario": "CI",
                "case_id": "test_ci_001",
                "dialog_history": [
                    {"turn": 0, "role": "Judge", "message": "现在开庭。"}
                ]
            }
        }
    ]

    for case in test_cases:
        print(f"\n--- Testing {case['name']} ---")
        try:
            response = requests.post(url, json=case['payload'], headers=headers, timeout=30)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    resp_json = response.json()
                    print("Response JSON:")
                    print(json.dumps(resp_json, ensure_ascii=False, indent=2))
                    
                    # Basic validation
                    if "response" in resp_json and "message" in resp_json["response"]:
                        print(f"✅ {case['name']} Passed")
                    else:
                        print(f"⚠️ {case['name']} Warning: Response format might be incorrect.")
                except json.JSONDecodeError:
                    print("Error: Failed to decode JSON response.")
                    print("Raw response:", response.text)
            else:
                print(f"❌ {case['name']} Failed: Server returned status {response.status_code}")
                print("Response:", response.text)

        except requests.exceptions.RequestException as e:
            print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    test_api()




