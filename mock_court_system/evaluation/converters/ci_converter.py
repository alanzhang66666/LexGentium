import re
from typing import List, Dict, Any
from .base_converter import BaseConverter

class CIConverter(BaseConverter):
    """
    Converter for CI (Court Judgment) scenario.
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
            if line.startswith('[conv]') or line.startswith('法律调解对话'):
                continue

            # Try to identify speaker
            role = ""
            msg = line
            
            # Format 1: 角色A（审判长）：... or 角色A（审判长）: ...
            match = re.search(r'^角色[ABC]（(.+?)）[：:](.*)', line)
            if match:
                role = match.group(1)
                msg = match.group(2)
            
            # Format 2: Judge：... or Judge: ...
            if not role:
                match = re.search(r'^(Judge|Plaintiff|Defendant|审判长|原告|被告)[：:](.*)', line, re.IGNORECASE)
                if match:
                    role = match.group(1)
                    msg = match.group(2)

            # Format 3: 角色A：... (Infer from A/B/C)
            if not role:
                match = re.search(r'^(角色[ABC])[：:](.*)', line)
                if match:
                    r_code = match.group(1)
                    msg = match.group(2)
                    if "角色A" in r_code: role = "审判长"
                    elif "角色B" in r_code: role = "原告"
                    elif "角色C" in r_code: role = "被告"

            if role:
                if current_role:
                    dialog_history.append({
                        "turn": turn,
                        "role": self._map_role(current_role),
                        "content": "\n".join(current_message).strip()
                    })
                    turn += 1
                
                current_role = role
                current_message = [msg.strip()]
            else:
                 if current_role:
                    current_message.append(line)

        if current_role:
            dialog_history.append({
                "turn": turn,
                "role": self._map_role(current_role),
                "content": "\n".join(current_message).strip()
            })
            
        return dialog_history

    def _map_role(self, raw_role: str) -> str:
        if "审判长" in raw_role or "Judge" in raw_role:
            return "Judge"
        if "原告" in raw_role or "Plaintiff" in raw_role:
            return "Plaintiff"
        if "被告" in raw_role or "Defendant" in raw_role:
            return "Defendant"
        return "Unknown"

    def parse_document(self, file_path: str) -> Dict[str, Any]:
        """
        Parse Civil Judgment (判决书).
        Expected structure for J1Bench:
        {
            "judgment_result": "..." # Full text or specific section usually
            # CI Evaluator needs 'judgment_result' to compare.
            # It also analyzes the dialog history for PFS (Procedural Fairness Score).
        }
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # CI Evaluator primarily looks at "judgment_result"
        # We can provide the Full Text or extract "判决如下"
        
        # Extract "判决如下" section
        result = self._extract_section(content, [r"判决如下", r"判决结果"], [r"审判长", r"$", r"附："])
        
        if not result:
            result = content # Fallback to full content if extraction fails
            
        return {
            "judgment_result": result, # Main field for comparison
            "full_document": content
        }
