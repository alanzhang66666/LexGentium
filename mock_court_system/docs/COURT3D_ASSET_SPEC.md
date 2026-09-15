# 3D 法庭角色资产规范

正式模型按 `3D建模方案/涉外模拟法庭人物性转版生成档案.md` 制作后，只需替换 `public/court3d/casts/foreign_commercial.json` 里对应 `skins.*.model` 路径。运行时加载器支持 `.glb` / `.gltf` / `.vrm`；路径为空或加载失败时回退到胶囊占位人。

## 替换流程（审判长验证）

1. 将文件放到 `public/court3d/models/judge_presiding_m.vrm`（或 `.glb`）。
2. 确认剧组 JSON 中 `roles.judge.skins.swap.model` 已指向该路径（默认已写好）。
3. 打开 `/court3d` 进入会话。若模型合法，审判长席位显示 VRM；否则继续显示胶囊人 + 名牌。
4. 对照 `checklist` 验收：整齐短黑发、椭圆偏方脸、深红领襟、银灰签字笔、冷静直视。

大体积文件不要提交进 git，使用 Git LFS 或对象存储。

## 规格

| 项 | 主角 | 配角 |
| --- | --- | --- |
| 三角面 | ≤ 40k | ≤ 15k |
| 贴图 | 皮肤 2K + 服装 2K，分材质 | 合并 1K–2K |
| 骨骼 | VRM Humanoid 或 Mixamo 命名 | 同 |
| 表情 | 52 ARKit BlendShape | 最少 A/I/U/E/O + 眨眼 |
| 口型 | viseme 15 组 | 5 元音 |
| 视线 | 眼球骨或 lookAt | 可选 |
| 挂点 | 右手（笔）、左手（卷宗）、桌面 | 按需 |
| 格式 | glTF 2.0 或 VRM 1.0，建议 Draco | 同 |
| 单文件 | ≤ 8MB（Draco 后） | ≤ 5MB |

## 禁用

木槌（默认）、法官假发、欧美陪审团、英式律师袍、夸张国旗墙、影视化囚服、族裔刻板印象。开庭/宣判用口头宣布 + 起立。

## 剧组席位

`foreign_commercial`：审判长、书记员、中方代理律师、中方企业代表、外方代理律师、外方企业代表、口译员。
