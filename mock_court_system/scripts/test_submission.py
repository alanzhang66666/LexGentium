import requests
import json
import os

def test_submission_server():
    # 1. Read submission.json
    submission_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "submission.json")
    if not os.path.exists(submission_path):
        print(f"❌ submission.json not found at {submission_path}")
        return

    with open(submission_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    base_url = config.get("api_key", "").rstrip("/")
    headers = config.get("headers", {})
    
    if not base_url:
        print("❌ No URL found in 'api_key' field of submission.json")
        return

    print(f"Testing Server URL: {base_url}")

    # 2. Construct Test Payloads
    test_cases = [
        {
            "name": "CI Scenario (Judge)",
            "payload": {
                "scenario": "CI",
                "case_id": "TEST-CI-001",
                "input_json": {
                    "id": "TEST-CI-001",
                    "plaintiff_info": {
                        "name": "测试原告",
                        "address": "测试地址",
                        "representative": "张三"
                    },
                    "defendant_info": {
                        "name": "测试被告",
                        "address": "测试地址",
                        "sex": "男"
                    },
                    "third_party_findings": "这是一个测试案例。原告借给被告100元，被告未还。"
                },
                "dialog_history": [
                    {"role": "Judge", "message": "现在开庭。请原告核实身份信息。"}
                ]
            }
        },
        {
            "name": "CD Scenario (Plaintiff Lawyer)",
            "payload": {
                "scenario": "CD",
                "case_id": "TEST-CD-001",
                "input_json": {
                    "id": "CD-1",
                    "template": "民事起诉状...",
                    "ground_truth": "..."
                },
                "dialog_history": [
                    {"role": "Lawyer", "message": "您好，我是您的代理律师。请问您想要起诉谁？"},
                    {"role": "Client", "message": "我要起诉李四，他欠钱不还。"}
                ]
            }
        },
        {
            "name": "CD Scenario (Simple)",
            "payload": {
                "scenario": "CD",
                "case_id": "TEST-CD-002",
                "input_json": {
                    "id": "CD-2",
                    "template": "民事起诉状...",
                    "ground_truth": "..."
                },
                "dialog_history": []
            }
        },
        {
            "name": "DD Scenario (Defendant Lawyer)",
            "payload": {
                "scenario": "DD",
                "case_id": "TEST-DD-001",
                "input_json": {
                    "case_info": {"case_number": "（2024）某民初1号", "court": "某某法院"},
                    "complaint": {
                        "plaintiff_claim": ["还钱"],
                        "plaintiff_case_description": "被告欠原告100元未还。"
                    }
                },
                "dialog_history": [
                    {"role": "Lawyer", "message": "您好，我是您的代理律师。请问您对起诉有什么意见？"},
                    {"role": "Client", "message": "我没欠他钱，早就还了。"}
                ]
            }
        }
    ]

    # 3. Send Requests
    for case in test_cases:
        print(f"\n{'='*50}")
        print(f"Testing {case['name']}...")
        try:
            response = requests.post(f"{base_url}", json=case['payload'], headers=headers, timeout=30)
            
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                print("✅ Server responded successfully!")
                try:
                    print("Response Body:")
                    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
                except:
                    print("Response Text:", response.text)
            else:
                print("❌ Server returned error.")
                print("Response Text:", response.text)

        except Exception as e:
            print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    test_submission_server()
