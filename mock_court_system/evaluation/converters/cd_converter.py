import re
from typing import List, Dict, Any
from .base_converter import BaseConverter

class CDConverter(BaseConverter):
    """
    Converter for CD (Civil Complaint) scenario.
    """
    
    def parse_dialog(self, file_path: str) -> List[Dict[str, Any]]:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split by speakers roughly
        # Assuming format "Role: Message" or "Name (Role): Message"
        lines = content.split('\n\n')
        dialog_history = []
        turn = 0
        
        # Simple finite state machine or line iteration
        # Since the format provided in example is: 
        # 律师：...
        # 彭峰超（客户）：...
        
        # We'll split by newlines and try to merge multi-line messages
        lines = content.split('\n')
        
        current_role = ""
        current_message = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if line starts with a role indicator
            role_match = re.match(r'^(律师|[^（]+（客户）)：(.*)', line)
            
            if role_match:
                # Save previous message
                if current_role:
                    dialog_history.append({
                        "turn": turn,
                        "role": self._map_role(current_role),
                        "message": "\n".join(current_message).strip()
                    })
                    turn += 1
                
                # Start new message
                current_role = role_match.group(1)
                current_message = [role_match.group(2).strip()]
            else:
                # Continuation of previous message
                if current_role:
                    current_message.append(line)
                    
        # Add last message
        if current_role:
            dialog_history.append({
                "turn": turn,
                "role": self._map_role(current_role),
                "message": "\n".join(current_message).strip()
            })
            
        return dialog_history

    def _map_role(self, raw_role: str) -> str:
        if "律师" in raw_role:
            return "Lawyer"
        if "客户" in raw_role:
            return "Client"
        return "Unknown"

    def parse_document(self, file_path: str) -> Dict[str, Any]:
        """
        Parse Civil Complaint (起诉状).
        Expected structure for J1Bench CD Evaluator ground truth:
        {
          "specific_characters": {
              "plaintiff": {"name": ..., "gender": ..., ...},
              "defendant": {"name": ..., ...}
          },
          "claims": [...], # List of strings
          "case_details": "...", # Facts and reasons
          "evidence": [...] # List of strings
        }
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 1. Plaintiff Info
        plaintiff_section = self._extract_section(content, [r"原告："], [r"被告："])
        plaintiff_info = self._parse_party_info(plaintiff_section)
        
        # 2. Defendant Info
        defendant_section = self._extract_section(content, [r"被告："], [r"诉讼请求："])
        defendant_info = self._parse_party_info(defendant_section)
        
        # 3. Claims
        claims_text = self._extract_section(content, [r"诉讼请求："], [r"事实与理由：", r"事实和理由："])
        claims = [line.strip() for line in claims_text.split('\n') if line.strip()]
        
        # 4. Facts/Case Details
        facts = self._extract_section(content, [r"事实与理由：", r"事实和理由："], [r"此致", r"证据", r"附："])
        
        # 5. Evidence
        evidence_text = self._extract_section(content, [r"附：证据清单", r"证据：", r"证据清单"], [r"$"])
        evidence = [line.strip() for line in evidence_text.split('\n') if line.strip()]
        
        # Construct result
        return {
            "specific_characters": {
                "plaintiff": plaintiff_info,
                "defendant": defendant_info
            },
            "claims": claims,
            "case_details": facts,
            "evidence": evidence
        }

    def _parse_party_info(self, text: str) -> Dict[str, str]:
        """
        Heuristic parsing of party info.
        Example: "创华金有限公司 住所地： ... 法定代表人： 彭峰超 ..."
        """
        info = {
            "name": "",
            "gender": "",
            "birth_date": "",
            "nation": "",
            "address": "",
            "representative": "" # For company
        }
        
        # Try to find Name (usually at the start or after "原告/被告：")
        # In the provided example: "原告： 创华金有限公司 住所地..."
        # The text passed here is " 创华金有限公司 住所地： ..."
        
        # Split by known keys
        keys = ["住所地：", "法定代表人：", "性别：", "出生日期：", "民族：", "统一社会信用代码："]
        
        # Extract Name (everything before the first key)
        first_key_idx = len(text)
        for key in keys:
            idx = text.find(key)
            if idx != -1 and idx < first_key_idx:
                first_key_idx = idx
        
        info["name"] = text[:first_key_idx].strip()
        
        # Extract other fields
        if "住所地：" in text:
            info["address"] = self._extract_field(text, "住所地：", keys)
        if "法定代表人：" in text:
            info["representative"] = self._extract_field(text, "法定代表人：", keys)
        if "性别：" in text:
            info["gender"] = self._extract_field(text, "性别：", keys)
        if "民族：" in text:
            info["nation"] = self._extract_field(text, "民族：", keys)
        if "出生日期：" in text:
            info["birth_date"] = self._extract_field(text, "出生日期：", keys)
            
        return info

    def _extract_field(self, text: str, field_key: str, all_keys: List[str]) -> str:
        start = text.find(field_key)
        if start == -1:
            return ""
        start += len(field_key)
        
        # Find the nearest next key
        end = len(text)
        for k in all_keys:
            idx = text.find(k, start)
            if idx != -1 and idx < end:
                end = idx
        
        return text[start:end].strip()




