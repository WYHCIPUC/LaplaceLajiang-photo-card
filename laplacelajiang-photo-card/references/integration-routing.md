# Integration routing

本 skill 的统一入口把“自建风格”和“参考项目结果形态”放在同一个缩略图画廊里。输入图片后，先分析素材，再为目录中的每个条目生成低成本缩略图；用户选定后，才进入高清生成。`integrated-preset-catalog.json` 是执行时唯一数据源，`style-presets.md` 只承载人类可读说明。

## 路由类型

### Native preset

直接读取 `style-presets.md` 中的视觉骨架、适用条件和禁止项。适合用户只想选择材质、色彩或抽象语言的情况。

### Reference-result preset

读取 `integrated-preset-catalog.json` 的 `source_project`、`native_skill`、`native_policy`、`adapter` 和 `output_form`，再叠加当前照片的证据矩阵。它默认调用“结果适配器”，不是外部仓库的运行时依赖：

- `native_policy=explicit-only`：本机存在对应 skill 且用户明确要求原生流程时，才切换；
- `native_policy=adapter-only`：始终使用本 skill 适配器；
- `source_status` 或 `license_status` 标记为 `unverified`：强制保持 `adapter-only`，不得下载、执行或复制对应仓库内容；
- 默认仍由本 skill 统一生成缩略图、等待选择、输出高清卡片和执行 QA；
- 视频类参考项目只映射到静帧、关键帧或版式逻辑，不自动生成视频；
- 外部项目的示例图、私有提示词、品牌资产和受限代码不能进入本整合包。

## 组合规则

用户可以选择一个结果形态和一个视觉语言，例如：

- `scene-card-archive` + `paper-collage-halftone`：场景档案结构 + 半调纸张材质；
- `photo-abstraction-study` + `eastern-silk-cinema`：抽象研究图结构 + 绢本氛围；
- `shot-recipe-keyframe` + `retro-travel-collage`：电影关键帧结构 + 复古旅行拼贴。

如果两个预设的文字结构、主体位置或版权边界冲突，优先保留用户照片真实性和证据矩阵，再减少装饰层。

组合只允许“一种结果形态 + 一种视觉语言”。不要叠加两个结果形态或两个高强度材质预设；如果用户选择不兼容组合，保留第一项为主，第二项只提取色彩和材质。

## Prompt assembly

缩略图和高清提示词按固定顺序组装：

1. 同一份照片事实与证据矩阵；
2. 主预设的 `output_form`、`layout` 和 `prompt_kernel`；
3. blend 预设仅提供 `theme` 和材质词；
4. 目录 `defaults.guardrails`；
5. 缩略图或高清阶段限定；
6. “不生成精确文字，交给后期合成”。

不得从外部仓库临时复制提示词作为运行输入。

## 统一输出

每次运行保存：

1. `analysis.md`：来源分析和证据矩阵；
2. `previews/`：每个注册预设一张缩略图或失败占位卡；
3. `previews/style-gallery.png`：完整画廊；
4. `prompts/`：缩略图提示和选定风格高清提示；
5. `final/`、`layers/`：只在用户确认后生成；
6. `session.json` 与 `selection.lock.json`：可恢复状态与高清生成门禁；
7. `metadata.json`、`materials.md`、`qa-report.md`：记录所选适配器和实际生成状态。
