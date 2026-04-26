"""
状态机实现
用于 CI 场景的庭审流程控制

增强版：支持子阶段追踪、程序合规检查和统一状态导出，
消除 API 层与状态机之间的语义偏差。
"""
from .schemas import CourtState, CourtSubStage


class StateMachine:
    """庭审流程状态机"""

    def __init__(self):
        self.current_state = CourtState.OPENING
        self.current_sub_stage = CourtSubStage.OPENING_IDENTITY
        self.state_history = [self.current_state]
        self.sub_stage_history = [self.current_sub_stage]
        self._opening_completed = False

        # 程序合规追踪：记录每个阶段的必经步骤是否完成
        self.compliance_log: list = []

        # 状态转移表
        self.transitions = {
            CourtState.OPENING: (
                self._check_opening_complete,
                CourtState.INVESTIGATION,
            ),
            CourtState.INVESTIGATION: (
                self._check_investigation_complete,
                CourtState.DEBATE,
            ),
            CourtState.DEBATE: (
                self._check_debate_complete,
                CourtState.MEDIATION,
            ),
            CourtState.MEDIATION: (
                self._check_mediation_complete,
                CourtState.JUDGMENT,
            ),
            CourtState.JUDGMENT: (
                lambda: True,
                CourtState.CLOSED,
            ),
        }

        # 各阶段子状态
        self.opening_phase = {
            "plaintiff_verified": False,
            "defendant_verified": False,
            "court_composition_announced": False,
            "procedure_announced": False,
            # 权利义务告知
            "rights_informed_mask": {"plaintiff": False, "defendant": False},
            # 回避申请
            "recusal_asked_mask": {"plaintiff": False, "defendant": False},
            # 缺席后果
            "absence_asked_mask": {"plaintiff": False, "defendant": False},
        }

        self.investigation_phase = {
            "plaintiff_stated": False,
            "defendant_responded": False,
            "evidence_round": 0,
            "no_more_evidence": {"plaintiff": False, "defendant": False},
            "fact_inquiry_mask": {"plaintiff": False, "defendant": False}, # 法庭事实核实/发问
            # 质证逻辑
            "waiting_for_cross_exam": False,
            "last_evidence_provider": None, # 'plaintiff' or 'defendant'
            # 多轮质证/辩论追踪
            "current_discussion": {
                "is_active": False,
                "topic": None,
                "topic_signature": None,
                "last_speaker_role": None,
                "pending_question": None,
                "burden_holder": None, # 'plaintiff' or 'defendant'
                "round_count": 0,
                "repeat_count": 0
            },
            "closed_topics": [],
            "last_discussion_result": None # 记录上一轮讨论的结论（如：原告举证失败）
        }

        self.debate_phase = {
            "focus_summarized": False,
            "plaintiff_debated": False,
            "defendant_debated": False,
            "final_statement": {"plaintiff": False, "defendant": False},
            # 多轮辩论追踪
            "waiting_for_rebuttal": False,
            "current_topic": {
                "is_active": False,
                "point": None,
                "last_speaker_role": None,
                "burden_holder": None, # 'plaintiff' or 'defendant'
                "round_count": 0
            },
            "last_discussion_result": None
        }

        self.mediation_phase = {
            "asked": False,
            "plaintiff_response": None,
            "defendant_response": None,
            "announced": False,
        }

    def _check_opening_complete(self) -> bool:
        """检查开庭阶段是否完成"""
        p = self.opening_phase
        return (
            p["plaintiff_verified"]
            and p["defendant_verified"]
            and p["court_composition_announced"]
            and p["procedure_announced"]
            and all(p["rights_informed_mask"].values())
            and all(p["recusal_asked_mask"].values())
            and all(p["absence_asked_mask"].values())
        )

    def _check_investigation_complete(self) -> bool:
        """检查法庭调查阶段是否完成"""
        p = self.investigation_phase
        return (
            p["plaintiff_stated"]
            and p["defendant_responded"]
            and p["no_more_evidence"]["plaintiff"]
            and p["no_more_evidence"]["defendant"]
            and all(p["fact_inquiry_mask"].values())
            and not p["waiting_for_cross_exam"]
        )

    def _check_debate_complete(self) -> bool:
        """检查法庭辩论阶段是否完成"""
        p = self.debate_phase
        return (
            p["focus_summarized"]
            and p["plaintiff_debated"]
            and p["defendant_debated"]
            and p["final_statement"]["plaintiff"]
            and p["final_statement"]["defendant"]
        )

    def _check_mediation_complete(self) -> bool:
        """检查调解阶段是否完成"""
        p = self.mediation_phase
        return (
            p["asked"]
            and p["plaintiff_response"] is not None
            and p["defendant_response"] is not None
            and p["announced"]
        )

    def try_transition(self) -> bool:
        """尝试状态转移"""
        checker, nxt = self.transitions.get(
            self.current_state,
            (None, None),
        )
        if checker and checker():
            self._log_compliance(self.current_state, "stage_complete")
            self.current_state = nxt
            self.state_history.append(nxt)
            self._sync_sub_stage()
            return True
        self._sync_sub_stage()
        return False

    def mark_opening_complete(self):
        self._opening_completed = True

    def update_phase_status(self, **kwargs):
        """更新当前阶段的子状态"""
        if self.current_state == CourtState.OPENING:
            self.opening_phase.update(kwargs)
        elif self.current_state == CourtState.INVESTIGATION:
            self.investigation_phase.update(kwargs)
        elif self.current_state == CourtState.DEBATE:
            self.debate_phase.update(kwargs)
        elif self.current_state == CourtState.MEDIATION:
            self.mediation_phase.update(kwargs)
        self._sync_sub_stage()

    # ---------- 子阶段同步 ----------

    def _sync_sub_stage(self):
        """根据当前主阶段和子状态，计算精确的子阶段"""
        prev = self.current_sub_stage
        s = self.current_state

        if s == CourtState.OPENING:
            self.current_sub_stage = self._calc_opening_sub()
        elif s == CourtState.INVESTIGATION:
            self.current_sub_stage = self._calc_investigation_sub()
        elif s == CourtState.DEBATE:
            self.current_sub_stage = self._calc_debate_sub()
        elif s == CourtState.MEDIATION:
            self.current_sub_stage = self._calc_mediation_sub()
        elif s == CourtState.JUDGMENT:
            self.current_sub_stage = CourtSubStage.JUDGMENT_GENERATING
        elif s == CourtState.CLOSED:
            self.current_sub_stage = CourtSubStage.JUDGMENT_DONE

        if self.current_sub_stage != prev:
            self.sub_stage_history.append(self.current_sub_stage)

    def _calc_opening_sub(self) -> CourtSubStage:
        p = self.opening_phase
        if not (p["plaintiff_verified"] and p["defendant_verified"]):
            return CourtSubStage.OPENING_IDENTITY
        if not p["court_composition_announced"]:
            return CourtSubStage.OPENING_COMPOSITION
        if not p["procedure_announced"]:
            return CourtSubStage.OPENING_COMPOSITION
        if not all(p["rights_informed_mask"].values()):
            return CourtSubStage.OPENING_RIGHTS
        if not all(p["recusal_asked_mask"].values()):
            return CourtSubStage.OPENING_RECUSAL
        if not all(p["absence_asked_mask"].values()):
            return CourtSubStage.OPENING_ABSENCE
        return CourtSubStage.OPENING_DONE

    def _calc_investigation_sub(self) -> CourtSubStage:
        p = self.investigation_phase
        if not p["plaintiff_stated"]:
            return CourtSubStage.INVESTIGATION_CLAIM
        if not p["defendant_responded"]:
            return CourtSubStage.INVESTIGATION_DEFENSE
        if p["waiting_for_cross_exam"]:
            return CourtSubStage.INVESTIGATION_CROSS_EXAM
        if not (p["no_more_evidence"]["plaintiff"] and p["no_more_evidence"]["defendant"]):
            return CourtSubStage.INVESTIGATION_EVIDENCE
        if not all(p["fact_inquiry_mask"].values()):
            return CourtSubStage.INVESTIGATION_FACT_INQUIRY
        return CourtSubStage.INVESTIGATION_DONE

    def _calc_debate_sub(self) -> CourtSubStage:
        p = self.debate_phase
        if not p["focus_summarized"]:
            return CourtSubStage.DEBATE_FOCUS
        if p.get("waiting_for_rebuttal"):
            return CourtSubStage.DEBATE_REBUTTAL
        if not (p["plaintiff_debated"] and p["defendant_debated"]):
            return CourtSubStage.DEBATE_ARGUMENT
        if not (p["final_statement"]["plaintiff"] and p["final_statement"]["defendant"]):
            return CourtSubStage.DEBATE_FINAL_STATEMENT
        return CourtSubStage.DEBATE_DONE

    def _calc_mediation_sub(self) -> CourtSubStage:
        p = self.mediation_phase
        if not p["asked"]:
            return CourtSubStage.MEDIATION_ASK
        if p["plaintiff_response"] is None:
            return CourtSubStage.MEDIATION_PLAINTIFF_RESP
        if p["defendant_response"] is None:
            return CourtSubStage.MEDIATION_DEFENDANT_RESP
        if not p["announced"]:
            return CourtSubStage.MEDIATION_ANNOUNCE
        return CourtSubStage.MEDIATION_DONE

    # ---------- 程序合规日志 ----------

    def _log_compliance(self, state: CourtState, event: str):
        self.compliance_log.append({
            "state": state.value,
            "sub_stage": self.current_sub_stage.value,
            "event": event,
        })

    def get_compliance_report(self) -> dict:
        """返回程序合规检查报告：哪些必经步骤完成了、哪些跳过了。"""
        report = {
            "opening": {
                "identity_verified": self.opening_phase["plaintiff_verified"] and self.opening_phase["defendant_verified"],
                "composition_announced": self.opening_phase["court_composition_announced"],
                "procedure_announced": self.opening_phase["procedure_announced"],
                "rights_informed": all(self.opening_phase["rights_informed_mask"].values()),
                "recusal_asked": all(self.opening_phase["recusal_asked_mask"].values()),
                "absence_warned": all(self.opening_phase["absence_asked_mask"].values()),
            },
            "investigation": {
                "plaintiff_stated": self.investigation_phase["plaintiff_stated"],
                "defendant_responded": self.investigation_phase["defendant_responded"],
                "evidence_rounds": self.investigation_phase["evidence_round"],
                "all_evidence_done": all(self.investigation_phase["no_more_evidence"].values()),
                "fact_inquiry_done": all(self.investigation_phase["fact_inquiry_mask"].values()),
            },
            "debate": {
                "focus_summarized": self.debate_phase["focus_summarized"],
                "plaintiff_debated": self.debate_phase["plaintiff_debated"],
                "defendant_debated": self.debate_phase["defendant_debated"],
                "final_statements": self.debate_phase["final_statement"],
            },
            "mediation": {
                "asked": self.mediation_phase["asked"],
                "plaintiff_response": self.mediation_phase["plaintiff_response"],
                "defendant_response": self.mediation_phase["defendant_response"],
                "announced": self.mediation_phase["announced"],
            },
            "stages_visited": [s.value for s in self.state_history],
            "sub_stages_visited": [s.value for s in self.sub_stage_history],
        }
        return report

    # ---------- J1-EVAL PFS 实时合规追踪 ----------

    def get_realtime_compliance(self) -> dict:
        """返回 J1-EVAL 风格的实时合规状态：
        每个阶段列出所有必经动作及完成情况。"""

        stages = {}

        # Opening 阶段动作
        p = self.opening_phase
        stages["opening"] = {
            "actions": [
                {"action": "verify_plaintiff_identity", "label": "核实原告身份",
                 "completed": p["plaintiff_verified"], "required": True},
                {"action": "verify_defendant_identity", "label": "核实被告身份",
                 "completed": p["defendant_verified"], "required": True},
                {"action": "announce_court_composition", "label": "宣布审判组成",
                 "completed": p["court_composition_announced"], "required": True},
                {"action": "announce_procedure", "label": "告知适用程序",
                 "completed": p["procedure_announced"], "required": True},
                {"action": "inform_plaintiff_rights", "label": "告知原告权利义务",
                 "completed": p["rights_informed_mask"]["plaintiff"], "required": True},
                {"action": "inform_defendant_rights", "label": "告知被告权利义务",
                 "completed": p["rights_informed_mask"]["defendant"], "required": True},
                {"action": "ask_plaintiff_recusal", "label": "询问原告回避申请",
                 "completed": p["recusal_asked_mask"]["plaintiff"], "required": True},
                {"action": "ask_defendant_recusal", "label": "询问被告回避申请",
                 "completed": p["recusal_asked_mask"]["defendant"], "required": True},
                {"action": "warn_plaintiff_absence", "label": "告知原告缺席后果",
                 "completed": p["absence_asked_mask"]["plaintiff"], "required": True},
                {"action": "warn_defendant_absence", "label": "告知被告缺席后果",
                 "completed": p["absence_asked_mask"]["defendant"], "required": True},
            ],
        }

        # Investigation 阶段动作
        inv = self.investigation_phase
        stages["investigation"] = {
            "actions": [
                {"action": "plaintiff_statement", "label": "原告陈述诉讼请求和事实",
                 "completed": inv["plaintiff_stated"], "required": True},
                {"action": "defendant_response", "label": "被告答辩",
                 "completed": inv["defendant_responded"], "required": True},
                {"action": "plaintiff_evidence_done", "label": "原告举证完毕",
                 "completed": inv["no_more_evidence"]["plaintiff"], "required": True},
                {"action": "defendant_evidence_done", "label": "被告举证完毕",
                 "completed": inv["no_more_evidence"]["defendant"], "required": True},
                {"action": "cross_examination_resolved", "label": "质证完成",
                 "completed": not inv["waiting_for_cross_exam"], "required": True},
                {"action": "plaintiff_fact_inquiry", "label": "法庭向原告核实事实",
                 "completed": inv["fact_inquiry_mask"]["plaintiff"], "required": True},
                {"action": "defendant_fact_inquiry", "label": "法庭向被告核实事实",
                 "completed": inv["fact_inquiry_mask"]["defendant"], "required": True},
            ],
            "evidence_rounds": inv["evidence_round"],
        }

        # Debate 阶段动作
        deb = self.debate_phase
        stages["debate"] = {
            "actions": [
                {"action": "summarize_focus", "label": "归纳争议焦点",
                 "completed": deb["focus_summarized"], "required": True},
                {"action": "plaintiff_debate", "label": "原告辩论",
                 "completed": deb["plaintiff_debated"], "required": True},
                {"action": "defendant_debate", "label": "被告辩论",
                 "completed": deb["defendant_debated"], "required": True},
                {"action": "plaintiff_final_statement", "label": "原告最后陈述",
                 "completed": deb["final_statement"]["plaintiff"], "required": True},
                {"action": "defendant_final_statement", "label": "被告最后陈述",
                 "completed": deb["final_statement"]["defendant"], "required": True},
            ],
        }

        # Mediation 阶段动作
        med = self.mediation_phase
        stages["mediation"] = {
            "actions": [
                {"action": "ask_mediation_willingness", "label": "询问调解意愿",
                 "completed": med["asked"], "required": True},
                {"action": "plaintiff_mediation_response", "label": "原告调解回应",
                 "completed": med["plaintiff_response"] is not None, "required": True},
                {"action": "defendant_mediation_response", "label": "被告调解回应",
                 "completed": med["defendant_response"] is not None, "required": True},
                {"action": "announce_mediation_result", "label": "宣布调解结果",
                 "completed": med["announced"], "required": True},
            ],
        }

        # 计算 PFS
        total_required = 0
        total_completed = 0
        stage_scores = {}
        warnings = []

        for stage_name, stage_data in stages.items():
            actions = stage_data["actions"]
            required = [a for a in actions if a.get("required")]
            completed = [a for a in required if a["completed"]]
            score = len(completed) / len(required) if required else 1.0
            stage_scores[stage_name] = round(score, 4)
            total_required += len(required)
            total_completed += len(completed)

            # 检查已到达但未完成的阶段中的遗漏
            stage_enum_map = {
                "opening": CourtState.OPENING,
                "investigation": CourtState.INVESTIGATION,
                "debate": CourtState.DEBATE,
                "mediation": CourtState.MEDIATION,
            }
            stage_enum = stage_enum_map.get(stage_name)
            if stage_enum and stage_enum in self.state_history:
                for a in required:
                    if not a["completed"]:
                        current_idx = list(CourtState).index(self.current_state) if self.current_state in CourtState else 0
                        expected_idx = list(CourtState).index(stage_enum) if stage_enum in CourtState else 0
                        if current_idx > expected_idx:
                            warnings.append({
                                "type": "skipped_action",
                                "stage": stage_name,
                                "action": a["action"],
                                "label": a["label"],
                                "severity": "high",
                            })

        pfs_score = total_completed / total_required if total_required > 0 else 0.0

        return {
            "current_stage": self.current_state.value,
            "current_sub_stage": self.current_sub_stage.value,
            "pfs_score": round(pfs_score, 4),
            "stage_completion_rates": stage_scores,
            "stages": stages,
            "warnings": warnings,
            "stages_visited": [s.value for s in self.state_history],
            "sub_stages_visited": [s.value for s in self.sub_stage_history],
        }

    # ---------- 统一状态导出 ----------

    def export_state(self) -> dict:
        """导出状态机当前状态的完整快照，供 API 层直接使用，
        消除 API 层自行猜测阶段的需求。"""
        return {
            "current_stage": self.current_state.value,
            "current_sub_stage": self.current_sub_stage.value,
            "stage_label": self._human_readable_stage(),
            "is_finished": self.current_state in (CourtState.CLOSED, CourtState.JUDGMENT),
        }

    def _human_readable_stage(self) -> str:
        mapping = {
            CourtState.OPENING: "opening",
            CourtState.INVESTIGATION: "investigation",
            CourtState.DEBATE: "debate",
            CourtState.MEDIATION: "mediation",
            CourtState.JUDGMENT: "judgment",
            CourtState.CLOSED: "finished",
        }
        return mapping.get(self.current_state, "unknown")
