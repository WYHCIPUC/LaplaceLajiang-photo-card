---
name: laplacelajiang-photo-card
description: Turn one or more user photos into premium editorial cards through a gated exhibition workflow, or package the same 24 visual directions as a no-Codex consumer prompt product for platforms such as Doubao, Kimi and Qwen. Analyze source evidence, route images through every native and reference-result preset, build an immersive selection gallery when requested, render only locked high-resolution selections, or export platform-adapted prompts, sample images, offline copy tools, instructions, correction prompts, licensing notes and a sale-ready ZIP without the gallery. Use for photo beautification, stylization, collage, art direction, visual cards, posters, style comparison, immersive selection, prompt products, digital goods, or bundled reference-project result formats.
---

# LaplaceLajiang Photo Card

把自建视觉预设和参考项目结果适配器整合为一个统一入口。始终执行“领取入场券 → 全量缩略图巡展 → 用户收藏 1–6 幅 → 逐幅高清装裱 → 取件交付”，不要把缩略图当成最终成品。

用户明确要求面向未安装 Codex 的买家、豆包／Kimi／千问提示词、数字商品或无展厅版本时，切换为“消费级提示词商品”分支：默认只交付一个完全自包含的离线 HTML，把 24 张样图、平台适配词、三档强度、双参考模式、修复词、简明教程、平台限制、隐私和授权说明全部内嵌；不生成展厅，也不要求买家安装 skill。只有用户明确要求源文件、可编辑数据或完整开发包时，才附加 Markdown、JSON、说明目录和 ZIP。

首次使用或环境变化后，先运行 `python scripts/photo_card.py doctor`。日常操作只使用 `scripts/photo_card.py` 统一入口；底层脚本用于生成与诊断。

## 核心门禁

1. 不覆盖或改写用户原图。
2. 先读取 [references/integrated-preset-catalog.json](references/integrated-preset-catalog.json)，再运行 `scripts/check_preset_catalog.py`。
3. 为目录中的每个预设生成缩略图；失败项重试一次，仍失败时在画廊中保留占位卡并标注失败原因。
4. 用 `scripts/manage_session.py select` 记录用户明确选择。没有 `selection.lock.json` 时，禁止进入高清生成。
5. 只对锁定的一个或多个预设生成高清素材；精确文字交给 `scripts/compose_card.py`。
6. 最终运行 `scripts/validate_delivery.py` 和人工视觉检查；任何失败都不能标记为完成。

## 工作流

### 0. 消费级提示词商品包分支

仅在用户明确要求无 Codex 商品版、平台提示词包或数字商品时使用。先确保样图目录包含目录中的全部 24 个 `<preset-id>.png`，并确认样图均来自用户自有或当前项目生成素材；不得打包参考仓库 showcase 图片。

默认先生成内部完整数据包，再收束成买家只需打开的单文件页面：

```powershell
python scripts/photo_card.py consumer-pack --preview-dir <24张样图目录> --source-image <测试原图> --output <新的商品目录>
python scripts/photo_card.py consumer-page --source-pack <内部商品目录> --output <交付目录>/LaplaceLajiang-照片风格提示词.html
```

最终买家目录默认只能包含一个 `.html` 文件。页面必须内嵌全部 24 张压缩样图和全部提示词，首屏用三步说明直接告诉买家如何使用；卡片只显示样图、单行标题、简短定位和“复制当前提示词／双参考强风格／下载参考图／风格不够／出现文字／主体跑偏”按钮，不把长提示词默认铺在页面上。平台、强度、教程、平台必须能真正出图、双参考上传顺序、结果差异、隐私、授权和不包含会员／额度等必要信息必须在同一页面内可访问。页面离线打开时不得依赖网络字体、脚本、图片或框架。

内部提示词数据仍必须包含通用／豆包／Kimi／千问四套平台词、保真优先／平衡推荐／强烈实验三档强度、图 1 锁内容且图 2 取视觉语法的双参考词和每风格专属的风格强化／去文字／主体保真三条重试词。每条完整提示词必须包含该风格不可省略的成品配方、原图绑定、事实锁定、构图、媒介材质、色彩光线、细节层级、特别避免项、全局禁止项和明确输出指令；不得仅用一条风格形容句叠加通用保真段，也不得用“分析步骤”语言诱导模型输出分析板。Kimi 文案必须区分视觉理解与创意设计生图插件；豆包和千问文案必须要求进入明确支持参考图或图片编辑的模式。不要承诺不同平台像素级复刻，不包含平台账号、会员、额度或 API Key。

### 1. 建立会话与证据矩阵

优先使用统一入口创建递增版本目录：

```powershell
python scripts/photo_card.py start --source <图片> --output-root <输出根目录> --slug <名称>
```

多图时重复 `--source`，第一张为主图。入口会校验图片、拒绝重复输入、保存原图副本、按 EXIF 方向记录有效尺寸，并冻结 `catalog.snapshot.json` 与 `selection-map.json`。已有明确空目录时才直接使用 `scripts/manage_session.py init`。检查所有输入图，记录尺寸、方向、主辅图、主体、姿态、前中后景、遮挡、负空间、方向、主色、强调色、文字安全区和不确定区域。

把事实写入 `analysis.md` 的“观察事实 → 设计映射”矩阵。抽象符号、标签、裁片、数据和故事都必须能回溯到矩阵；无法确认的内容改成定性表达或留白。

### 2. 生成全量缩略图

读取目录中全部预设：

- `native_presets` 决定独立视觉语言；
- `reference_result_presets` 决定参考项目的结果形态和适配器；
- `prompt_kernel`、`layout`、`theme` 和全局 `guardrails` 共同形成提示词。

缩略图必须使用同一主图、同一证据矩阵和统一比例，只比较结果形态、构图、材质、色彩与抽象程度。使用低分辨率，避免精细文字、复杂纹理和最终级修复。把每张图保存为 `previews/<preset-id>.png`，并用 `scripts/manage_session.py mark-preview` 记录成功或失败。

所有缩略图状态确定后，使用统一入口一次生成两种画廊：

```powershell
python scripts/photo_card.py gallery <delivery>
```

`previews/style-gallery.html` 是默认入口，必须是真正的 Three.js 桌面展馆：深色木质前厅、黄铜门把、母片、自动入场靠近、正对主墙的固定策展位，以及向后收束的侧廊纵深。入场后相机、建筑与灯光保持稳定，右侧“下一幅”以约 850ms 光幕逐幅切换，不能让整座展馆平移或旋转；方向键是补充。只验收 1366×768 及以上桌面宽屏，不制作移动布局。主界面不出现自由行走或无障碍参观按钮。

“展品名册”必须是放在胡桃木阅读台上的亚麻硬壳书：先见封面，再翻开双页，每跨页 4 幅、共 6 章，具有真实翻页动效并可直达展品。“镜语室”提供 24 式索引、基础／进阶配方与复制按钮。所有标题在墙签、名册、细看层和技术回退中单行完整显示，空间不足时动态缩小字号，不能换行或省略。

点击作品或按 E 打开温暖细看层：展厅作为可辨认的虚化背景，左侧为编号、标题、简洁说明、风格、来源和收藏操作，右侧按原图比例完整展示展品，横图、竖图和方图均不得裁切；支持按住比较母片、细节镜缩放／拖动，以及画框有限摆动、离墙深度和阻尼回正。收藏袋先复核 1–6 幅展品，再通过 localhost 状态桥写入选择锁；页面只读取真实包装状态，不得用定时器伪造高清生成。完成后每幅至少交付高清母版、3:4 小红书版、展签、生成记录和质检记录。空间统一使用暖象牙灰泥、真实 PBR 浅色白橡木、2700K 展灯与冷色暮光、深色红木／旧黄铜画框和现代直线侧挡板。二维版仅作为技术回退，静态 PNG 负责分享与打印。具体规则见 [references/immersive-gallery.md](references/immersive-gallery.md)。

展示画廊后暂停，等待用户把 1–6 幅作品加入收藏，并回复编号、`#编号`、预设 ID 或中英完整标签。编号始终读取本次会话的 `selection-map.json`，不得用当前全局目录推算。不得自行选型后继续高清生成。

### 3. 处理用户选择

把选择写入 `selection.lock.json`。优先使用统一入口，编号和 ID 均可：

```powershell
python scripts/photo_card.py select <delivery> 17 5 --blend 6
```

一次可带走 1–6 幅作品；每幅分别生成高清成品并保存在 `take-home/<编号>-<preset-id>/`。`--blend` 是整组共享的可选材质语言，只允许一个原生预设。冲突时依次保护：原图真实性、主体身份与姿态、证据矩阵、文字可读性、装饰效果。

用户上传临时参考时，按构图、材质、色彩、形式、字体气质和禁止项建立临时预设；只加入本次会话，不写回内置目录，除非用户明确要求固化。

### 4. 高清生成与原生路由

默认由本 skill 根据目录适配器生成高清设计素材。只有用户明确要求某个参考项目的“原生流程”、该 skill 已安装且许可证允许当前用途时，才切换到原生 skill；否则继续使用本 skill 的兼容适配器。

需要判断原生可用性时运行 `scripts/check_native_routes.py`。只有本机已安装、目录允许原生路由、来源未标为未核验且许可未标为未核验时，才报告 `native-available`。把结果写入本次 `materials.md`，不要把“有 GitHub 链接”误报为“本机已安装并可直接调用”。

视频类参考项目默认只适配静帧、关键帧或版式逻辑。除非用户另行明确请求视频，不生成视频、音频或动态素材。

高清提示词必须包含源图事实、选中预设的 `prompt_kernel`、全局 guardrails、文字安全区和禁止项。不得凭空增加人物、地标、产品、测量、历史背景、神话设定或精确文案。

### 5. 排版与交付

使用 `scripts/compose_card.py` 读取统一目录完成 `split`、`stacked`、`board` 或 `full-bleed` 版式。照片区域优先使用原始像素合成，AI 只生成设计面板或视觉处理层。标题、副标题、微文案、标签和日期全部后期排版。

保存：源图副本、缩略图、完整画廊、每幅高清生成素材、最终 PNG/JPG、可编辑图层、提示词、`session.json`、`selection.lock.json`、`metadata.json`、`materials.md` 和 `qa-report.md`。全部作品完成后运行 `python scripts/photo_card.py package <delivery>`，生成取件网页、取件单、哈希清单和 ZIP，并向用户明确报告绝对保存路径。目录规范见 [references/output-contract.md](references/output-contract.md)。

### 6. QA 与失败恢复

运行：

```powershell
python scripts/check_preset_catalog.py <skill-dir>
python scripts/photo_card.py validate <delivery>
```

人工检查主体可识别、身份和姿态未改变、原图区域未被 AI 重画、所有缩略图可区分、文字可读、裁片来自源图、数据和文化内容有依据、没有异常边缘或伪影。

随时运行 `python scripts/photo_card.py status <delivery> --list` 查看当前阶段、全部编号和下一步。旧版会话第一次继续时运行 `python scripts/photo_card.py migrate <delivery>`，按原预设顺序冻结兼容快照。图像生成失败时先标记 `failed`，保留已完成项和状态文件；排除问题后运行 `python scripts/photo_card.py resume <delivery>` 回到失败前阶段，只重试失败项，不从头重做。安全过滤重试时，用中性、事实性的服装、姿态和环境描述消除歧义，不改变用户内容。

## 资源导航

- [references/integrated-preset-catalog.json](references/integrated-preset-catalog.json)：唯一机器可读目录、主题、提示词内核和原生路由。
- [references/style-presets.md](references/style-presets.md)：目录中全部预设的中文视觉说明与边界。
- [references/integration-routing.md](references/integration-routing.md)：适配器、组合和原生调用规则。
- [references/inspiration-map.md](references/inspiration-map.md)：参考来源和许可边界。
- [references/output-contract.md](references/output-contract.md)：会话状态、交付结构和 QA 合同。
- [references/immersive-gallery.md](references/immersive-gallery.md)：沉浸式画廊的交互、无障碍、性能和原创边界。
- [scripts/manage_session.py](scripts/manage_session.py)：初始化、缩略图状态和选择锁。
- [scripts/photo_card.py](scripts/photo_card.py)：日常使用的统一入口，提供 `doctor`、`start`、`status`、`gallery`、`select`、`package`、`migrate`、`resume`、`validate` 和 `self-test`。
- [scripts/make_contact_sheet.py](scripts/make_contact_sheet.py)：从目录生成分组画廊。
- [scripts/build_exhibition_gallery.py](scripts/build_exhibition_gallery.py)：编排主展馆、无障碍回退、静态画廊与清单。
- [scripts/build_spatial_exhibition.py](scripts/build_spatial_exhibition.py)：生成零依赖第一人称 3D 展馆和优化后的墙面展品。
- [scripts/build_consumer_prompt_pack.py](scripts/build_consumer_prompt_pack.py)：生成不依赖 Codex、无展厅的 24 风格跨平台提示词商品包。
- [scripts/build_single_page_prompt_product.py](scripts/build_single_page_prompt_product.py)：把内部商品数据压缩为样图和提示词全部内嵌的单文件离线网页。
- [scripts/package_collection.py](scripts/package_collection.py)：核验多幅高清作品，生成取件处、取件单与 ZIP。
- [scripts/compose_card.py](scripts/compose_card.py)：目录驱动的最终排版。
- [scripts/validate_delivery.py](scripts/validate_delivery.py)：缩略图与最终交付验证。
- [scripts/check_preset_catalog.py](scripts/check_preset_catalog.py)：目录与 Markdown 注册表一致性检查。
- [scripts/check_native_routes.py](scripts/check_native_routes.py)：报告原生参考 skill 与兼容适配器的实际路由。

## 边界

- 不复制参考项目的 SKILL.md、私有提示词、示例图、品牌资产或受限代码。
- 不把外部 showcase 图片打包为本 skill 资产，不移除他人水印。
- 不未经授权发布到 GitHub、小红书或其他平台。
- 不把照片美化扩展成换脸、身份重写、无依据的场景生成或品牌仿冒。
