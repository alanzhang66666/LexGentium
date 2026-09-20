# 开源代码1

本项目参考引用的第三方开源代码快照，供法律智能体 / 庭审仿真与交互评测相关研发与评审查阅。
快照形式参考 `D:\lexcyber\开源代码`：每仓一个子目录、保留上游原始布局、不带 `.git`，
本 README 登记来源、版本与许可。夹内代码不参与本项目构建，改动请回上游仓库。

本夹与仓库根目录 `开源代码/`（`scripts/build_submission.py --item5` 装配的比赛提交快照）不是同一项。

| 目录 | 上游仓库 | 快照 commit | 许可 | 内容 |
| --- | --- | --- | --- | --- |
| `AgentCourt/` | [relic-yuexi/AgentCourt](https://github.com/relic-yuexi/AgentCourt) | `dd41c6c`（2024-09-05） | **无许可文件**，默认保留所有权利，仅供研究参考 | LLM 驱动的全流程庭审仿真：法官 / 原被告律师 / 书记员多智能体；对抗式进化律师；`EMDB/` 经验·案例·法条三库；`LLM/` 文心 / OpenAI / 智谱 / 离线等客户端 |
| `J1Bench/` | [FudanDISC/J1Bench](https://github.com/FudanDISC/J1Bench) | `61a6ea5`（2026-04-07） | **无许可文件**（README 徽章指向不存在的 `LICENSE`），默认保留所有权利，仅供研究参考 | J1-Envs 六个交互法律环境（KQ 知识问答、LC 法律咨询、CD 起诉状起草、DD 答辩状起草、CI 法庭调查、CR 刑事庭审）与 J1-Eval 评测脚本；论文 *Ready Jurist One*（ACL 2026） |

## 与本项目的关系

- 两仓都是 LLM 法律智能体：AgentCourt 用多智能体复现庭审并让律师在对抗仿真中积累经验；J1Bench 在程序规则下与多方角色交互，评测法律智能体。可对照本仓库工作台里的角色分工、提示词与本地任务引擎，**不是**定罪 / 量刑 LJP，也**不是**本产品的外发路径。
- 数据集不在夹内。AgentCourt 训练 / 测试案在 [Hugging Face · AgentCourt](https://huggingface.co/datasets/youzi517/AgentCourt)；J1Bench 评测集在 [Hugging Face · J1-Eval_Dataset](https://huggingface.co/datasets/CharlesBeaumont/J1-Eval_Dataset)，按上游 README 放到 `J1Bench/src/data/case/`。
- 两仓均未附许可证，引用其代码前需取得作者授权或仅作思路参考。配置里的 `api_key` / `YOUR_API_KEY` 均为占位符，不是可用密钥。
- AgentCourt 论文：[arXiv:2408.08089](https://arxiv.org/abs/2408.08089)。J1Bench 论文：[arXiv:2507.04037](https://arxiv.org/abs/2507.04037)。
