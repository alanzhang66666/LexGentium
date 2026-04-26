from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from typing import List, Optional

class RobustJsonOutputParser(JsonOutputParser):
    """
    A robust JSON output parser that can handle markdown code blocks
    and common JSON errors.
    """
    def parse(self, text: str) -> dict:
        # Clean up markdown code blocks if present
        text = text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        return super().parse(text)
