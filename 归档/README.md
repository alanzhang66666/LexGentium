# 项目材料归档

本目录只保存申报、商业计划、参考文献和从活文档挪出来的化石，**不是系统运行入口**。日常开发请使用 `mock_court_system/`（当前产品版本 **0.8.0**）。

申请书正文工作稿在 `申报材料/`：`申请书正文.md`、`申请书正文.docx`、`申请书正文-含图.docx`。插图在 `申报材料/figures/`。

## 目录

```text
归档/
├── 申报材料/                 # 启研计划终稿、工作稿、figures/
├── 商业计划与市场材料/       # LegalFlow 商计及分章扩写
├── 参考文献/                 # 核心论文 PDF
├── 技术报告/                 # 外仓对照稿 + 推理 v1 精简版
├── 工程化石/                 # 旧 76 项表、离线 API 备选
├── 评测化石/                 # 2026-04 旧跑数
└── README.md
```

`答辩与展示材料/` 因单文件超过 GitHub 100MB 限制，已在仓库 `.gitignore` 中排除，不纳入本目录。

## 申报材料

| 文件 | 说明 |
|------|------|
| `启研计划申请书-完整版.docx` | 启研计划申请书 Word 终稿（原 `(3)` 版） |
| `启研计划申请书-完整版.pdf` | 同上的 PDF 打印稿 |
| `依托单位推荐意见.docx` | 依托单位推荐意见 |
| `附图-扩展式博弈树与SPNE.png` | 申请书用扩展式博弈树图 |
| `市基金申请学科代码.pdf` | 北京市自然科学基金学科代码表 |
| `XX——基于LexGentium模拟法庭系统的国际商事仲裁程序论证与溯源审计智能体.docx` | 课题方案文稿，不是案例包 |
| `申请书正文.md` | 申请书 Markdown 工作稿（原 `mock_court_system/docs/`） |
| `申请书正文.docx` | 同上的 Word 工作稿 |
| `申请书正文-含图.docx` | 含图工作稿 |
| `figures/` | 申请书插图（原 `mock_court_system/docs/figures/`） |

## 商业计划与市场材料

| 文件 | 说明 |
|------|------|
| `LegalFlow商业计划书.docx` | 商业计划书总稿 |
| `市场痛点与机遇.docx` | 市场分析扩写 |
| `产品方案-第三部分与第九部分.docx` | 产品方案与财务相关章节 |
| `商业模式与财务-第五第六部分.docx` | 商业模式章节 |

## 技术报告

| 文件 | 说明 |
|------|------|
| `LexGentium-推理优化技术报告-详细版.md` | 对照 `Hanyuan9766/LexGentium` PR #2 的外仓稿。Phase 0/1 **已在本树**（`case_bundle` / 台账 / IRAC / `reasoning_meta`），不要拿这份稿当「未落地」说明 |
| `LEXGENTIUM_REASONING_OPTIMIZATION_REPORT.md` | 2026-09-10 v1 精简版（原 `mock_court_system/docs/`）。下一阶段清单已过时 |

## 工程化石 / 评测化石

| 路径 | 说明 |
|------|------|
| `工程化石/SYSTEM_STATUS_2026-09-11.md` | 旧 76 项表。现役是 `mock_court_system/docs/SYSTEM_STATUS.md` |
| `工程化石/API_ALTERNATIVES.md` | 离线最近邻备选 |
| `工程化石/API_RECONSTRUCTION.md` | 最近邻重建说明 |
| `评测化石/results/` | 2026-04 论文跑数。新报告写 `mock_court_system/evaluation/results/` |

## 参考文献

| 文件 | 论文 |
|------|------|
| `LexEval_2409.20288.pdf` | LexEval：中文法律 LLM 评测基准 |
| `J1-EVAL_2507.04037.pdf` | J1-EVAL / Ready Jurist One：动态法律智能体评测 |
| `AgentMediation_2509.06586.pdf` | AgentMediation：LLM 纠纷调解模拟 |
| `GameTheory_Meets_LLMs_2502.09053.pdf` | 博弈论 × LLM 综述 |
| `LegalDelta_2508.12281.pdf` | LegalΔ：法律推理强化学习 |
| `Intelligent_Legal_Assistant_2502.07904.pdf` | 交互式法律问答澄清系统 |

## 整理时已删除的内容

- 张晨钰另一课题的基金申请书（误放入本目录）
- 学信网截图（含身份证号等个人敏感信息）
- 申请书旧稿、同内容 `.doc` 重复件、未命名空模板
- 一次性公式修复脚本与申请书纯文本提取
- 目录中曾列出但不存在的 `执行摘要.docx`（正文工作稿现已放在本目录）
