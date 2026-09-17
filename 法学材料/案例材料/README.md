# 案例材料

微信收到的**原始案例文本与已填标注**，只读素材。不是运行入口，也**还不是** `mock_court_system/data/research_packs/` 那种正式研究包。

## 来源

2026-09-17 自微信文件目录 `…/xwechat_files/wxid_05nra012kxjx22_69ff/msg/file/2026-09/` 取压缩包入库。zip 未设 UTF-8 标志位（`flags=0x0000`），文件名按 GBK 原始字节还原后落盘。

| 原始压缩包 | MD5 | 压缩包字节 | 条目 | 去向 |
|---|---|---|---|---|
| `案例.zip` | `088c30f23e0938ee3dd2a9739a7163fc` | 6,494,395 | 36 | `案件1-9/` + `案例整理下载/` |
| `案例标注.zip` | `3bda088bea82701a7402d33c3a2c4675` | 1,628,585 | 40 | `案例标注/` |
| `案例(1).zip` | `84629cdd1aff8f1b41dd40978dd5c6a4` | 4,026,970 | 22 | **未入库**，见下 |

`案例(1).zip` 的 21 个文件与 `案例.zip/案例整理下载/` 的 21 个文件**逐条 CRC32 与字节长度相同**，是重复子集，未重复入库。解压时剔除 `.DS_Store`。

## 清单

```text
案例材料/
├── 案件1-9/          9 个编号案（7、8 号各含多份文书）   13 文件
├── 案例整理下载/      案例 19–28 + 11 份未编号原文        21 文件
└── 案例标注/          15 份标注 xlsx；样本案例1–6 另附
                      交付内容 docx 与原文                 33 文件
```

合计 **67 个文件**。

### 案件1-9

| 编号 | 文件 | 内容 |
|---|---|---|
| 1 | 1 | `[2020] SGHC 141` CDM and others v CDP |
| 2 | 1 | `[2022] SGHC 58` Re Shanghai Xinan Screenwall Building & Decoration |
| 3 | 1 | 艺术马赛克 v 佛山市宏冠贸易 |
| 4 | 1 | 斯芙拉玛特 v 张家港万晟新材料 |
| 5 | 1 | 爱迪玛 v 张家港万晟新材料 |
| 6 | 1 | 麦格理银行 v 万达控股集团 |
| 7 | 2 | UiPath v Shanghai Yunkuo（判决 / 意见与裁定） |
| 8 | 4 | Jiangsu Beier Decoration Materials v Angle World LLC（211028 / 221103 / 230718 / 240808） |
| 9 | 1 | Xin Yang International Import & Export v Azad International（意见与裁定） |

### 案例整理下载

- **编号案 19–28**（`案例19`–`案例28`）：蒙俄合资有色金属 v 西洲（上海）、BEIJING CRS、XIAMEN XIANGYU、`[2024] SGHCR 7` Wuhu Ruyi、BLOCKSTREAM、文森特·赫罗纳·易泽盖多 v 泰州远大、WS China v 四川荣丰、某某公司1 v 某某公司2、全球跨境贸易（新加坡）v 宁波海田、某设备公司 v 江阴某公司。
- **未编号原文 11 份**：Agerratum、Chenco Chemical、China Yantai Friction ×2、Huizhou Kailangde、Nantong Drayson、Shenzhen Lanteng、Shenzhen Yingfan、Shenzhen Zongheng ×2、Tianjin Dinghui。

### 案例标注

15 份 `01单篇标注` 已填表（另有 `02填写示例` 教学页）。"已填格"= B/C/D 列浅黄 `#FFF7DF` 内有值的格数，反映覆盖密度，**不等于**质量校验通过。

| 标注表 | 对应案例 | 已填格 | 标注人 | 独立复核 |
|---|---|---|---|---|
| `Beijing CRS … 案例20标注.xlsx` | 案例20 | 81 | 赵瞳心 2026-09-14 | 空 |
| `Wuhu Ruyi Xinbo … 案例22标注.xlsx` | 案例22（`[2024] SGHCR 7`） | 77 | 赵瞳心 2026-09-14 | 空 |
| `WS China Import GmbH … 案例25标注.xlsx` | 案例25 | 59 | **待填**（自注"AI 辅助初标稿，需实际标注人确认"） | 赵瞳心 9-14 |
| `Global Transit Trading … 案例27标注.xlsx` | 案例27 | 78 | 赵瞳心 2026-09-14 | 自注"UV：尚未安排独立复核" |
| `Huizhou Kailangde … .xlsx` | 未编号原文 | 58 | 王静怡 2026-09-14 | 空 |
| `Nantong Drayson … 标注.xlsx` | 未编号原文 | 58 | 王静怡 2026-09-14 | 空 |
| `Shenzhen Lanteng … 标注.xlsx` | 未编号原文 | 58 | 王静怡 2026-09-14 | 空 |
| `Shenzhen Yingfan … 标注.xlsx` | 未编号原文 | 58 | 王静怡 2026-09-14 | 空 |
| `Tianjin Dinghui Hongjun … 标注.xlsx` | 未编号原文 | 58 | 王静怡 2026-09-14 | 空 |
| `样本案例1/CEEG-LexGentium标注.xlsx` | CEEG (Shanghai) Solar v LUMOS | 61 | 林瓒 2026-09-14 | 空，日期"待填写" |
| `样本案例2/HNA-LexGentium标注.xlsx` | 245 Park Member v HNA Group (Intl) | 61 | 林瓒 2026-09-14 | 空 |
| `样本案例3/Liyu-LexGentium标注.xlsx` | Shanghai Liyu Optoelectronics v Brite Lite Tribe | 61 | 林瓒 2026-09-14 | 空 |
| `样本案例4/Qingdao-LexGentium标注.xlsx` | Qingdao FTZ Genius Intl Trading v P and S Intern | 61 | 林瓒 2026-09-14 | 空 |
| `样本案例5/Tianjin-LexGentium标注.xlsx` | Tianjin Port FTZ Intl Trade Service v Tiancheng Chempharm | 61 | 林瓒 2026-09-14 | 空 |
| `样本案例6/Weihai-LexGentium标注.xlsx` | Weihai Textile Group v Eruption Holdings | 61 | 林瓒 2026-09-14 | 空 |

九份顶层标注均能对上 `案例整理下载/` 里的原文；样本案例1–6 各含原文 pdf + docx、标注 xlsx、`<简称>-交付内容.docx`（交付说明含选案清单、研究问题、法源索引方向），与 `案例整理下载/` 无重名重复。

## 边界（下一轮不看到会做错）

1. **这些不是正式研究包。** 目录里没有 `pack.json`、没有 `documents/`、没有规则卡、没有原文锚点回填；`mock_court_system/data/research_packs/` 的正式包计数**仍为 0**（那两个 SAMPLE 是技术夹具）。只有原文本体与标注表，尚未转成运行时能消费的结构。
2. **15 份标注全部没有完成的独立复核。** 标注指南要求"由另一人独立复核"，现状：12 份复核格为空，案例27 自注"尚未安排独立复核"，案例25 更注明标注人是"待填（AI 辅助初标稿）"且复核格反而是赵瞳心。**不得把本目录当作已复核数据使用。**
3. **只覆盖 15 案。** `案件1-9/` 的 9 个编号案**没有任何配套标注**；`案例整理下载/` 的其余案也没有。
4. **标注内容未经本仓库校验。** 未跑过 `evaluation/` 的校验链，未核对标注表与 `<简称>-交付内容.docx` 是否一致；"已填格"只证明填了，不证明对。
5. **不要在这里改原文。** 本目录为只读素材；派生结果写进 `mock_court_system/` 下的运行时目录，不要污染原文。
6. 与 `法学材料/原始母表/` 的关系：母表是**候选来源**，本目录是**已下载的原文本体**，两者未做逐条对账。

## 待办

- 决定是否把 15 个已标案转成 `research_packs/` 结构（`pack.json` + `documents/`）；转换前先补独立复核。
- 补 `案件1-9/` 的标注，或明确其用途（若只作正文案例、不作研究包）。
- 与 `原始母表/计算法比赛-测试集+(2).xlsx`、`国际商事仲裁案件名案号网站汇总.docx` 对账，标出哪些候选已有原文。
