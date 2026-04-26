# API重建方案使用指南

## 概述

由于原始交互API已停用，本项目实现了基于历史数据的最近邻匹配方案来重建API功能。

### 核心思路

给定新输入 `x' = (scenario, case_id, dialog_history)`，系统会：
1. 在历史数据中查找最相似的输入 `x`
2. 返回对应的历史输出 `f(x)`

**优点**：
- 无需了解API内部逻辑
- 无需完整案例信息
- 实现简单，效果可预期

**局限性**：
- 没有随机性（相同输入总是返回相同输出）
- 存在歧义边界（相似但不完全匹配的情况）
- 依赖历史数据的质量和数量

## 使用步骤

### 1. 收集历史数据

从现有的结果文件中提取API交互历史：

```bash
python scripts/collect_api_history.py --output-dir ./output --data-dir ./api_history
```

这个脚本会：
- 读取 `output/CD_prediction.jsonl`、`DD_prediction.jsonl`、`CI_prediction.jsonl`
- 提取每轮对话的输入（dialog_history）和输出（API response）
- 保存到 `api_history/interactions.jsonl`

### 2. 启用API重建器

有两种方式启用：

#### 方式一：在代码中启用

```python
from core import CourtSimulatorClient

api_client = CourtSimulatorClient(
    base_url="http://...",
    api_key="...",
    use_reconstructor=True,  # 启用重建器
    reconstructor_data_dir="./api_history",  # 历史数据目录
)
```

#### 方式二：修改配置（推荐）

修改 `main.py` 中的初始化代码，添加重建器支持。

### 3. 运行系统

重建器会在以下情况自动启用：
- API调用失败（网络错误、超时等）
- API key未配置
- 主动启用时优先使用重建器

```bash
# 正常运行，如果API失败会自动fallback到重建器
python main.py --scenario CD --limit 1
```

## 工作原理

### 相似度计算

系统使用多维度相似度匹配：

1. **BM25关键词匹配**（权重50%）
   - 对对话历史进行分词
   - 使用BM25算法计算关键词相似度

2. **轮次相似度**（权重20%）
   - 比较对话轮次数
   - 轮次越接近，相似度越高

3. **最后消息相似度**（权重30%）
   - 使用Jaccard相似度比较最后一条消息
   - 考虑消息的语义相似性

### 匹配流程

```
新输入 x' = (scenario, case_id, dialog_history)
    ↓
提取场景相关的历史数据
    ↓
计算与每个历史输入的相似度
    ↓
选择相似度最高的历史输入 x
    ↓
返回对应的历史输出 f(x)
```

## 数据格式

### 历史数据存储格式

`api_history/interactions.jsonl` 每行一个JSON对象：

```json
{
  "scenario": "CD",
  "case_id": "123",
  "dialog_history": [
    {"turn": 0, "role": "Client", "message": "您好，我想要起草起诉状。"},
    {"turn": 1, "role": "Lawyer", "message": "好的，请告诉我您的姓名。"}
  ],
  "response": {
    "response": "我叫张三。"
  },
  "dialog_summary": "Client: 您好... | Lawyer: 好的...",
  "last_message": "好的，请告诉我您的姓名。",
  "turn_count": 2
}
```

## 性能优化

### 索引构建

系统会自动构建以下索引以加速查找：
- **场景索引**：按场景分组历史数据
- **BM25索引**：为每个场景构建关键词索引
- **向量索引**（可选）：如果使用嵌入模型

### 查找优化

- 只搜索相同场景的历史数据
- 使用最小相似度阈值过滤（默认0.1）
- 支持返回Top-K结果（默认只返回最相似的1个）

## 高级配置

### 自定义相似度阈值

```python
reconstructor = APIReconstructor(data_dir="./api_history")

# 查找最相似的结果，最小相似度0.3
results = reconstructor.find_nearest(
    scenario="CD",
    case_id="123",
    dialog_history=history,
    top_k=3,
    min_similarity=0.3,
)
```

### 查看统计信息

```python
stats = reconstructor.get_stats()
print(f"总交互数: {stats['total_interactions']}")
print(f"按场景分布: {stats['by_scenario']}")
```

## 注意事项

1. **数据质量**：历史数据越多、越全面，匹配效果越好
2. **相似度阈值**：如果匹配失败，可以降低 `min_similarity` 阈值
3. **场景隔离**：不同场景的数据不会相互匹配
4. **无随机性**：相同输入总是返回相同输出（这是设计特点）

## 故障排查

### 问题：找不到匹配结果

**原因**：
- 历史数据不足
- 相似度阈值过高
- 输入格式不匹配

**解决**：
1. 检查历史数据文件是否存在且包含数据
2. 降低 `min_similarity` 阈值
3. 确保输入格式与历史数据一致

### 问题：匹配结果不准确

**原因**：
- 历史数据质量不高
- 相似度计算不够精确

**解决**：
1. 收集更多高质量的历史数据
2. 考虑使用向量嵌入模型（需要额外配置）
3. 调整相似度权重

## 未来改进方向

1. **向量嵌入**：使用语义向量进行更精确的相似度计算
2. **多候选融合**：结合Top-K个候选结果，增加多样性
3. **增量学习**：自动从新交互中学习，更新历史数据
4. **缓存机制**：缓存常见输入的匹配结果，加速响应

