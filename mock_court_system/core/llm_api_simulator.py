"""
LLM API模拟器 - 使用LLM直接生成API回复
作为最近邻匹配的替代或补充方案

增强版：支持 top-k 检索增强生成 (RAG)、置信度评分和回退原因追踪。
"""
from typing import List, Dict, Optional
from .llm_client import LLMClient


class LLMAPISimulator:
    """使用LLM模拟API行为"""
    
    def __init__(self, llm: LLMClient, scenario: str = "CD"):
        self.llm = llm
        self.scenario = scenario
        
        self.scenario_prompts = {
            "CD": """你是一个模拟法庭API，扮演客户（Client）角色。
在起诉状生成场景中，你需要根据律师的问题提供真实、合理的客户回复。

回复要求：
1. 回复要自然、真实，符合普通客户的表达习惯
2. 信息要具体但可以适当模糊（如地址可以用××代替）
3. 如果律师问个人信息，提供合理的姓名、性别、出生日期等
4. 如果律师问案件情况，提供合理的案件描述
5. 如果信息不清楚，可以表示"记不太清楚"或"需要回去查找"
6. 保持对话的连贯性和逻辑性""",
            
            "DD": """你是一个模拟法庭API，扮演客户（Client）角色。
在答辩状生成场景中，你需要根据律师的问题提供真实、合理的客户回复。

回复要求：
1. 作为被告，需要针对起诉状内容进行回应
2. 可以承认、否认或部分承认原告诉求
3. 提供抗辩理由和事实依据
4. 回复要符合被告的立场和利益
5. 保持对话的连贯性和逻辑性""",
            
            "CI": """你是一个模拟法庭API，扮演原告（Plaintiff）或被告（Defendant）角色。
在法庭判决场景中，你需要根据审判长的问题提供真实、合理的当事人回复。

回复要求：
1. 根据角色（原告/被告）提供相应的回复
2. 陈述要符合法律程序要求
3. 提供事实、证据和法律依据
4. 保持法庭对话的正式性和逻辑性""",
        }
    
    def generate_response(
        self,
        scenario: str,
        case_id: str,
        dialog_history: List[Dict],
        input_json: Optional[Dict] = None,
        temperature: float = 0.7,
        reference_examples: Optional[List[Dict]] = None,
    ) -> Dict:
        """生成API回复，可选择性使用参考示例 (RAG)。"""
        system_prompt = self.scenario_prompts.get(scenario, self.scenario_prompts["CD"])
        
        dialog_text = self._format_dialog_history(dialog_history)
        
        user_prompt = f"案例ID: {case_id}\n\n对话历史:\n{dialog_text}\n\n"

        if reference_examples:
            user_prompt += "以下是相似历史交互供你参考（请学习其风格与模式，但不要照抄）：\n"
            for i, ref in enumerate(reference_examples, 1):
                ref_input = ref.get("input_summary", "")[:200]
                ref_output = ref.get("output", "")[:300]
                ref_sim = ref.get("similarity", 0)
                user_prompt += f"\n参考 {i}（相似度: {ref_sim:.2f}）:\n  输入: {ref_input}\n  输出: {ref_output}\n"
            user_prompt += "\n"

        user_prompt += "请根据上述对话历史和参考，生成符合场景的回复。回复要自然、真实，符合角色特点。"
        
        if input_json:
            case_info = self._format_case_info(input_json)
            user_prompt += f"\n\n案例信息:\n{case_info}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response_text = self.llm.chat_completion(messages, temperature=temperature)
            return {"response": response_text}
        except Exception as e:
            return {"error": str(e), "response": ""}
    
    def _format_dialog_history(self, dialog_history: List[Dict]) -> str:
        lines = []
        for item in dialog_history:
            role = item.get("role", "Unknown")
            message = item.get("message", "")
            turn = item.get("turn", "")
            if turn != "":
                lines.append(f"[轮次 {turn}] {role}: {message}")
            else:
                lines.append(f"{role}: {message}")
        return "\n".join(lines)
    
    def _format_case_info(self, input_json: Dict) -> str:
        info_parts = []
        for key, value in input_json.items():
            if isinstance(value, (str, int, float)):
                info_parts.append(f"{key}: {value}")
            elif isinstance(value, dict):
                info_parts.append(f"{key}: {self._format_case_info(value)}")
        return "\n".join(info_parts)


class HybridAPISimulator:
    """混合API模拟器 - top-k 检索增强生成 + 置信度 + 回退原因追踪"""
    
    def __init__(
        self,
        reconstructor,
        llm_simulator: LLMAPISimulator,
        similarity_threshold: float = 0.7,
        top_k: int = 3,
        low_confidence_threshold: float = 0.3,
    ):
        self.reconstructor = reconstructor
        self.llm_simulator = llm_simulator
        self.similarity_threshold = similarity_threshold
        self.top_k = top_k
        self.low_confidence_threshold = low_confidence_threshold
    
    def generate_response(
        self,
        scenario: str,
        case_id: str,
        dialog_history: List[Dict],
        input_json: Optional[Dict] = None,
    ) -> Dict:
        """生成API回复（top-k 检索增强策略）。"""
        results = self.reconstructor.find_nearest(
            scenario=scenario,
            case_id=case_id,
            dialog_history=dialog_history,
            top_k=self.top_k,
            min_similarity=0.05,
        )
        
        if not results:
            response = self.llm_simulator.generate_response(
                scenario=scenario,
                case_id=case_id,
                dialog_history=dialog_history,
                input_json=input_json,
                temperature=0.7,
            )
            response["_method"] = "llm_generation_no_history"
            response["_similarity"] = 0.0
            response["_confidence"] = 0.0
            response["_fallback_reason"] = "no_similar_history_found"
            response["_reference_examples"] = []
            return response

        best_interaction, best_similarity = results[0]

        if best_similarity >= self.similarity_threshold:
            response = best_interaction.response.copy()
            response["_method"] = "nearest_neighbor"
            response["_similarity"] = best_similarity
            response["_confidence"] = min(best_similarity, 1.0)
            response["_fallback_reason"] = None
            response["_reference_examples"] = [
                {"case_id": r[0].case_id, "similarity": r[1]}
                for r in results[:self.top_k]
            ]
            return response

        reference_examples = []
        for interaction, sim in results[:self.top_k]:
            ref_input = interaction.dialog_summary or interaction.last_message or ""
            ref_output = interaction.response.get("response", "")
            reference_examples.append({
                "input_summary": ref_input,
                "output": ref_output,
                "similarity": round(sim, 4),
                "case_id": interaction.case_id,
            })

        response = self.llm_simulator.generate_response(
            scenario=scenario,
            case_id=case_id,
            dialog_history=dialog_history,
            input_json=input_json,
            temperature=0.7,
            reference_examples=reference_examples,
        )

        avg_sim = sum(r[1] for r in results[:self.top_k]) / min(len(results), self.top_k)
        confidence = avg_sim * 0.6 + best_similarity * 0.4

        response["_method"] = "rag_generation"
        response["_similarity"] = best_similarity
        response["_confidence"] = round(confidence, 4)
        response["_reference_examples"] = [
            {"case_id": ref["case_id"], "similarity": ref["similarity"]}
            for ref in reference_examples
        ]

        if confidence < self.low_confidence_threshold:
            response["_fallback_reason"] = "low_confidence_needs_review"
            response["_needs_review"] = True
        else:
            response["_fallback_reason"] = "similarity_below_threshold_used_rag"
            response["_needs_review"] = False

        return response

