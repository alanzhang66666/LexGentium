import re
from typing import List, Dict, Any
from .base_converter import BaseConverter

class DDConverter(BaseConverter):
    """
    Converter for DD (Defense Statement) scenario.
    """
    
    def parse_dialog(self, file_path: str) -> List[Dict[str, Any]]:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.split('\n')
        dialog_history = []
        turn = 0
        current_role = ""
        current_message = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            role_match = re.match(r'^(律师|客户|[^：]+（做?被告）?)：(.*)', line)
            
            if role_match:
                if current_role:
                    dialog_history.append({
                        "turn": turn,
                        "role": self._map_role(current_role),
                        "message": "\n".join(current_message).strip()
                    })
                    turn += 1
                
                current_role = role_match.group(1)
                current_message = [role_match.group(2).strip()]
            else:
                if current_role:
                    current_message.append(line)
        
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
        return "Client"  # Assume anything else is the client/defendant

    def parse_document(self, file_path: str) -> Dict[str, Any]:
        """
        Parse Civil Defense Statement (答辩状).
        Expected structure for J1Bench DD Evaluator:
        {
          "specific_characters": {
              "defendant": {"name": ..., ...}
          },
          "statement_of_defence": "...", # The defense arguments
          "evidence": {
             "1": {"evidence": "...", "source": "..."},
             ...
          }
        }
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 1. Defendant Info
        # Usually starts with "答辩人（被告）：" or "答辩人："
        defendant_section = self._extract_section(content, [r"答辩人（被告）：", r"答辩人："], [r"答辩人因", r"一、"])
        defendant_info = self._parse_party_info(defendant_section)
        
        # 2. Defense Statement (Facts & Reasons)
        # J1Bench seems to lump "Facts and Reasons" into "statement_of_defence"
        # Or sometimes "Defense Opinions"
        defense_text = self._extract_section(content, [r"二、事实与理由", r"事实与理由", r"答辩如下："], [r"此致", r"附："])
        
        # 3. Evidence
        evidence_text = self._extract_section(content, [r"附：", r"证据材料"], [r"$"])
        evidence_dict = {}
        if evidence_text:
             evidence_lines = [line.strip() for line in evidence_text.split('\n') if line.strip()]
             for idx, line in enumerate(evidence_lines):
                 evidence_dict[str(idx+1)] = {"evidence": line, "source": ""}

        return {
            "specific_characters": {
                "defendant": defendant_info
            },
            "statement_of_defence": defense_text,
            "evidence": evidence_dict
        }

    def _parse_party_info(self, text: str) -> Dict[str, str]:
        info = {
            "name": "",
            "gender": "",
            "birth_date": "",
            "nation": "",
            "address": "",
            "representative": ""
        }
        
        keys = ["住所地：", "法定代表人：", "性别：", "出生日期：", "民族：", "职务："]
        
        first_key_idx = len(text)
        for key in keys:
            idx = text.find(key)
            if idx != -1 and idx < first_key_idx:
                first_key_idx = idx
        
        info["name"] = text[:first_key_idx].strip()
        
        if "住所地：" in text:
            info["address"] = self._extract_field(text, "住所地：", keys)
        if "法定代表人：" in text:
            info["representative"] = self._extract_field(text, "法定代表人：", keys)
            
        return info

    def _extract_field(self, text: str, field_key: str, all_keys: List[str]) -> str:
        start = text.find(field_key)
        if start == -1:
            return ""
        start += len(field_key)
        
        end = len(text)
        for k in all_keys:
            idx = text.find(k, start)
            if idx != -1 and idx < end:
                end = idx
        
        return text[start:end].strip()
