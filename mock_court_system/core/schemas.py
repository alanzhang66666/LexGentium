"""核心数据模型定义"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Literal, Dict, Any
from enum import Enum


# ========== 法庭角色枚举 ==========

class PartyRole(Enum):
    """参与角色"""
    JUDGE = "Judge"
    PLAINTIFF = "Plaintiff"
    DEFENDANT = "Defendant"
    LAWYER = "Lawyer"
    CLIENT = "Client"


class CourtState(Enum):
    """庭审状态"""
    OPENING = "S0_OPENING"
    INVESTIGATION = "S1_INVESTIGATION"
    DEBATE = "S2_DEBATE"
    MEDIATION = "S3_MEDIATION"
    JUDGMENT = "S4_JUDGMENT"
    CLOSED = "S5_CLOSED"


class CourtSubStage(Enum):
    """庭审子阶段 —— 细化每个主阶段内的必经步骤"""
    # 开庭准备子阶段
    OPENING_IDENTITY = "opening_identity"
    OPENING_COMPOSITION = "opening_composition"
    OPENING_RIGHTS = "opening_rights"
    OPENING_RECUSAL = "opening_recusal"
    OPENING_ABSENCE = "opening_absence"
    OPENING_DONE = "opening_done"
    # 法庭调查子阶段
    INVESTIGATION_CLAIM = "investigation_claim"
    INVESTIGATION_DEFENSE = "investigation_defense"
    INVESTIGATION_EVIDENCE = "investigation_evidence"
    INVESTIGATION_CROSS_EXAM = "investigation_cross_exam"
    INVESTIGATION_FACT_INQUIRY = "investigation_fact_inquiry"
    INVESTIGATION_DONE = "investigation_done"
    # 法庭辩论子阶段
    DEBATE_FOCUS = "debate_focus"
    DEBATE_ARGUMENT = "debate_argument"
    DEBATE_REBUTTAL = "debate_rebuttal"
    DEBATE_FINAL_STATEMENT = "debate_final_statement"
    DEBATE_DONE = "debate_done"
    # 调解子阶段
    MEDIATION_ASK = "mediation_ask"
    MEDIATION_PLAINTIFF_RESP = "mediation_plaintiff_resp"
    MEDIATION_DEFENDANT_RESP = "mediation_defendant_resp"
    MEDIATION_ANNOUNCE = "mediation_announce"
    MEDIATION_DONE = "mediation_done"
    # 判决
    JUDGMENT_GENERATING = "judgment_generating"
    JUDGMENT_DONE = "judgment_done"


class StructuredJudgment:
    """结构化判决/调解输出"""
    def __init__(self):
        self.facts: List[Dict[str, Any]] = []
        self.dispute_points: List[str] = []
        self.legal_articles: List[Dict[str, str]] = []
        self.liability_mapping: Dict[str, Any] = {}
        self.conclusion: str = ""
        self.mediation_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "dispute_points": self.dispute_points,
            "legal_articles": self.legal_articles,
            "liability_mapping": self.liability_mapping,
            "conclusion": self.conclusion,
            "mediation_result": self.mediation_result,
        }


# ========== 个人和组织信息 ==========

@dataclass
class PersonInfo:
    """自然人信息"""
    name: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[str] = None  # 出生日期
    ethnicity: Optional[str] = None  # 民族
    address: Optional[str] = None

    def get_missing_fields(self) -> List[str]:
        """获取缺失的必填字段"""
        missing = []
        if not self.name:
            missing.append("姓名")
        if not self.gender:
            missing.append("性别")
        if not self.dob:
            missing.append("出生日期")
        if not self.ethnicity:
            missing.append("民族")
        if not self.address or "待核" in self.address:
            missing.append("详细住址")
        return missing


@dataclass
class OrgInfo:
    """法人信息"""
    name: Optional[str] = None
    address: Optional[str] = None
    legal_rep: Optional[str] = None  # 法定代表人

    def get_missing_fields(self) -> List[str]:
        """获取缺失的必填字段"""
        missing = []
        if not self.name:
            missing.append("单位名称")
        if not self.address or "待核" in self.address:
            missing.append("单位住所地")
        if not self.legal_rep:
            missing.append("法定代表人姓名")
        return missing


# ========== 案件信息 ==========

@dataclass
class CaseInfo:
    """案件基本信息"""
    case_number: str = ""
    case_id: str = ""
    court_name: str = ""
    plaintiff_name: str = ""
    defendant_name: str = ""
    case_type: str = ""
    claim_amount: Optional[float] = None
    claim_description: str = ""
    third_party_findings: str = ""
    plaintiff_info: Dict[str, str] = field(default_factory=dict)
    defendant_info: Dict[str, str] = field(default_factory=dict)


@dataclass
class CaseData:
    """案件完整数据（用于DD场景）"""
    case_number: str = ""
    court_name: str = ""
    plaintiff_claims: List[str] = field(default_factory=list)
    plaintiff_facts: str = ""

    user_role: Literal["原告", "被告", "未知"] = "被告"
    user_entity_type: Literal["自然人", "法人", "未知"] = "未知"

    person_info: PersonInfo = field(default_factory=PersonInfo)
    org_info: OrgInfo = field(default_factory=OrgInfo)

    defense_claims: List[str] = field(default_factory=list)
    facts: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)

    last_reasoning: str = ""
    plaintiff_identity: str = ""

    def get_missing_mandatory_fields(self) -> List[str]:
        """返回必须追问的基础信息"""
        if self.user_entity_type == "自然人":
            return self.person_info.get_missing_fields()
        elif self.user_entity_type == "法人":
            return self.org_info.get_missing_fields()
        else:
            return ["主体类型(是个人还是公司)"]


# ========== 证据 ==========

@dataclass
class Evidence:
    """证据结构"""
    evidence_id: str
    provider: PartyRole
    content: str
    purpose: str
    opponent_opinion: Optional[str] = None


# ========== 对话消息 ==========

@dataclass
class Message:
    """对话记录"""
    role: PartyRole
    content: str
    timestamp: str
    state: Optional[CourtState] = None


@dataclass
class DialogTurn:
    """对话轮次"""
    turn: int
    role: str
    message: str


# ========== API 请求响应 ==========

@dataclass
class SimulateRequest:
    """模拟法庭 API 请求"""
    scenario: str
    key: str
    case_id: str
    dialog_history: List[Dict[str, Any]]


@dataclass
class SimulateResponse:
    """模拟法庭 API 响应"""
    scenario: str
    key: str
    case_id: str
    response: str
    status_code: Optional[int] = None
    error: Optional[str] = None


# ========== 提交结果 ==========

@dataclass
class SubmissionResult:
    """提交结果格式"""
    team_id: str
    case_id: str
    dialog_history: List[Dict[str, Any]]
    model_answer: Any  # CD/DD 是文本，CI 是字典


@dataclass
class CDModelAnswer:
    """CD 场景模型答案（起诉状）"""
    complaint_text: str


@dataclass
class DDModelAnswer:
    """DD 场景模型答案（答辩状）"""
    defense_text: str


@dataclass
class CIModelAnswer:
    """CI 场景模型答案（判决书）"""
    court_reasoning: str
    court_judgment: str
    law: List[str]
