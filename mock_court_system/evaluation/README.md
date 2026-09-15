# evaluation/

Web 对照、研究量表、论文实验、旧跑数曾经叠在这一层。2026-09-15 拆成四块。3D 不经过这里。

| 夹 / 文件 | 标签 | 干什么 |
|-----------|------|--------|
| `run_evaluation.py` | LIVE | `POST /evaluate` 和 `python evaluation/run_evaluation.py` |
| `lib/` | LIVE + RESEARCH | LexEval / J1 / CADD / `research_rubric.py` |
| `lab/legacy/` | LAB | `CD.py` `DD.py` `CI.py` `game_eval.py`。Web 不用 |
| `converters/` `adapters/` `evaluators/` | LIVE | 对照链 |
| `eval_config.yaml` | LIVE | 路径与阈值 |
| `data/test_run/` | LIVE 夹具 | 对照小样 |
| `results/` | LIVE 输出 | **新**对照报告写这里。不要提交 |
| `lab/` | LAB | 论文批跑。新实验输出写 `evaluation/results/`（时间戳目录） |
| `fossil/` | 指针 | 2026-04 旧跑数已去仓库根 `归档/评测化石/results/` |

## 现役入口

```bash
# Web 同一套
python evaluation/run_evaluation.py

# 论文实验（不是 Web）
python evaluation/lab/run_two_step_small_sample.py
python evaluation/lab/run_core_experiment_50.py
```

旧数字在 [`归档/评测化石/results/`](../../归档/评测化石/results/)。外仓对照稿里的旧路径不要改，那是历史记录。
