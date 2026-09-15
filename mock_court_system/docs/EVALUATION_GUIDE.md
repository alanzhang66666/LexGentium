# 评测指南（LexGentium 0.8）

## 主路径（Web / API）

日常复盘走工作台 **`/evaluation`** 三栏：对照、策略推演、程序合规。对照对应 **`POST /evaluate`**（Next：`POST /api/evaluate`）。后端任务执行 **`evaluation/run_evaluation.py`**，指标在 **`evaluation/lib/`**（LexEval、J1-EVAL、outcome、multi_layer、CADD 等）。

目录（2026-09-16）：对照链留在 `evaluation/` 根上；论文脚本在 `evaluation/lab/`；2026-04 旧跑数在仓库根 `归档/评测化石/results/`。详见 [`evaluation/README.md`](../evaluation/README.md)。

有 `links.game_id` 时，复盘「策略推演」还可打 `POST /game/{id}/evaluate/*`（结果 / 综合 / LexEval / J1Eval / CADD 责任链）。

```bash
# 与 API 任务同一套评测入口（离线也可直接跑）
cd mock_court_system
python evaluation/run_evaluation.py
```

`main.py` 与下面的 `scripts/evaluate_hybrid_solution.py` **只用于批跑 / 混合方案实验**，不是 Web 主路径。

---

## 附录：混合方案批跑

用于评估混合 API 模拟器与标准答案的相似度，**不**替代 `POST /evaluate`。

## 评测流程

### 1. 准备标准答案数据集

标准答案数据集应包含3个场景（CD、DD、CI），每个场景20条数据。

数据格式（JSONL）：
```json
{
  "id": "CD-1",
  "scenario": "CD",
  "dialog_history": [
    {"turn": 0, "role": "Client", "message": "您好，我想要起草起诉状。"},
    {"turn": 1, "role": "Lawyer", "message": "您好，我是您的代理律师..."},
    {"turn": 2, "role": "Client", "message": "我叫张三..."},
    ...
  ],
  "input_json": {...}  // 可选，案例输入信息
}
```

### 2. 运行评测

#### 基本用法

```bash
# 评测所有场景（CD、DD、CI）
python scripts/evaluate_hybrid_solution.py

# 指定数据目录
python scripts/evaluate_hybrid_solution.py --data-dir "../cail2025_智能体模拟法庭-复赛阶段-数据集"

# 只评测特定场景
python scripts/evaluate_hybrid_solution.py --scenarios CD DD

# 限制评测数量（快速测试）
python scripts/evaluate_hybrid_solution.py --limit 5
```

#### 配置混合方案参数

```bash
# 调整相似度阈值（默认0.7）
python scripts/evaluate_hybrid_solution.py --hybrid-threshold 0.8

# 只使用最近邻（不使用LLM）
python scripts/evaluate_hybrid_solution.py --use-reconstructor --no-use-llm

# 只使用LLM生成（不使用最近邻）
python scripts/evaluate_hybrid_solution.py --no-use-reconstructor --use-llm
```

### 3. 查看评测结果

评测完成后会生成两个文件：

1. **详细报告** (`evaluation_report_YYYY-MM-DDTHH-MM-SS.json`)
   - 包含所有评测细节
   - JSON格式，便于程序分析

2. **简要报告** (`evaluation_summary_YYYY-MM-DDTHH-MM-SS.txt`)
   - 人类可读的文本格式
   - 包含关键指标摘要

## 评测指标

### 总体指标

- **总轮次**: 评测的总对话轮数
- **完全匹配**: 相似度 ≥ 0.95 的回复数量
- **相似匹配**: 相似度 ≥ 0.7 的回复数量
- **不同匹配**: 相似度 < 0.7 的回复数量
- **完全匹配率**: 完全匹配 / 总轮次
- **相似匹配率**: (完全匹配 + 相似匹配) / 总轮次
- **平均相似度**: 所有回复的平均相似度分数

### 方法分布

显示每种方法（最近邻、LLM生成、混合）的使用次数和平均相似度：
- `nearest_neighbor`: 最近邻匹配
- `llm_generation`: LLM直接生成
- `hybrid`: 混合方案（根据相似度选择）

### 场景指标

每个场景（CD、DD、CI）的独立指标：
- 案例数
- 总轮次
- 完全匹配率
- 相似匹配率
- 平均相似度

## 评测示例

### 示例1：完整评测

```bash
python scripts/evaluate_hybrid_solution.py \
    --data-dir "../cail2025_智能体模拟法庭-复赛阶段-数据集" \
    --scenarios CD DD CI \
    --hybrid-threshold 0.7 \
    --output ./evaluation_results
```

### 示例2：快速测试（前5个案例）

```bash
python scripts/evaluate_hybrid_solution.py \
    --limit 5 \
    --scenarios CD
```

### 示例3：对比不同阈值

```bash
# 阈值0.6（更多使用LLM）
python scripts/evaluate_hybrid_solution.py --hybrid-threshold 0.6 --output ./results_threshold_0.6

# 阈值0.8（更多使用最近邻）
python scripts/evaluate_hybrid_solution.py --hybrid-threshold 0.8 --output ./results_threshold_0.8
```

## 评测报告解读

### 报告结构

```json
{
  "evaluation_time": "2025-01-XX...",
  "total_cases": 60,
  "total_turns": 1200,
  "overall_metrics": {
    "total_turns": 1200,
    "exact_matches": 800,
    "similar_matches": 300,
    "different_matches": 100,
    "exact_match_rate": 0.667,
    "similar_match_rate": 0.917,
    "avg_similarity": 0.852,
    "method_distribution": {
      "nearest_neighbor": 600,
      "llm_generation": 400,
      "hybrid": 200
    },
    "avg_similarity_by_method": {
      "nearest_neighbor": 0.920,
      "llm_generation": 0.750,
      "hybrid": 0.880
    }
  },
  "scenario_metrics": {
    "CD": {...},
    "DD": {...},
    "CI": {...}
  },
  "detailed_results": [...]
}
```

### 关键指标解读

1. **完全匹配率 > 60%**: 说明方案效果很好
2. **相似匹配率 > 90%**: 说明大部分回复都接近标准答案
3. **平均相似度 > 0.8**: 说明整体质量较高
4. **方法分布**: 可以分析哪种方法使用更多，效果更好

## 优化建议

### 根据评测结果调整参数

1. **如果最近邻匹配效果好**:
   - 提高 `hybrid_threshold`（如0.8）
   - 增加历史数据量

2. **如果LLM生成效果好**:
   - 降低 `hybrid_threshold`（如0.6）
   - 优化LLM提示词

3. **如果整体相似度低**:
   - 检查标准答案数据格式
   - 调整相似度计算算法
   - 增加历史数据质量

## 注意事项

1. **数据格式**: 确保标准答案数据包含完整的 `dialog_history`
2. **LLM配置**: 需要正确配置LLM API key和base_url
3. **历史数据**: 最近邻匹配需要先收集历史数据
4. **评测时间**: 完整评测可能需要较长时间（取决于数据量和LLM响应速度）

## 故障排查

### 问题：未找到标准答案数据

**解决**:
- 检查数据目录路径
- 确认文件格式正确（JSONL）
- 检查文件是否包含 `dialog_history` 字段

### 问题：LLM生成失败

**解决**:
- 检查LLM配置（api_key、base_url）
- 检查网络连接
- 查看错误日志

### 问题：相似度计算异常

**解决**:
- 检查文本编码
- 确认jieba分词正常
- 查看详细错误信息

## 进阶使用

### 自定义评测器

```python
from core.offline.evaluator import APISimulatorEvaluator

# 自定义相似度阈值
evaluator = APISimulatorEvaluator(
    similarity_threshold_exact=0.98,  # 完全匹配阈值
    similarity_threshold_similar=0.75,  # 相似匹配阈值
)
```

### 分析详细结果

```python
import json

# 加载评测报告
with open("evaluation_report_xxx.json", "r", encoding="utf-8") as f:
    report = json.load(f)

# 分析特定场景
cd_results = [r for r in report["detailed_results"] if r["scenario"] == "CD"]

# 分析低相似度案例
low_similarity = [r for r in report["detailed_results"] if r["similarity_score"] < 0.5]
```

