# Output contract

## Delivery directory

每次运行创建独立版本目录，禁止覆盖已有交付：

```text
delivery-vNN/
  sources/
    primary.<ext>
    secondary-01.<ext>
  previews/
    <preset-id>.png
    style-gallery.html
    style-gallery-accessible.html
    style-gallery.png
    gallery-manifest.json
    打开廿四境展厅.cmd
    exhibition/
      gallery-runtime.js
      gallery.css
      vendor/
      textures/
      assets/
        mother-plate.webp
        artworks/
          <preset-id>.webp
  generated/
    <selected-preset>-design.png
  take-home/
    packing-status.json
    index.html
    取件单.md
    collection-manifest.json
    laplacelajiang-collection.zip
    <number>-<preset-id>/
      final/
        master.png
        xhs-3x4.jpg
        editorial-card.png
        editorial-card.jpg
      layers/
        photo-primary.png
        design-panel.png
        text-overlay.png
      metadata.json
      展签.md
      generation-record.json
      qa-record.json
  prompts/
    thumbnail-prompts.md
    final-prompt.md
  analysis.md
  catalog.snapshot.json
  selection-map.json
  session.json
  selection.lock.json
  metadata.json
  materials.md
  qa-report.md
```

缩略图阶段不创建 `generated/`、`final/` 和 `layers/`。用户确认后才创建这些目录。

## Session states

`session.json` 的 `stage` 只能按以下顺序前进：

```text
initialized → previewing → awaiting-selection → selected → rendering → complete
                                      ↘ failed
```

- `preview_status` 为每个注册预设保存 `pending`、`complete` 或 `failed`。
- `awaiting-selection` 表示画廊完整，允许存在明确标注的失败占位卡。
- `selection.lock.json` 包含 1–6 个按收藏顺序排列的 `items`、兼容字段 `primary_preset`、`blend_presets`、`selected_at` 和目录 SHA-256。
- `catalog.snapshot.json` 固定本次画廊的预设版本；后续 skill 更新不得改变既有会话的编号、提示词或选择锁。
- `selection-map.json` 保存连续编号、预设 ID、中英标签和类别，使用户可以直接回复 `3`、`#3` 或预设 ID。
- `rendering` 与 `complete` 必须有有效选择锁；否则 QA 失败。

## Metadata minimum fields

```json
{
  "skill": "laplacelajiang-photo-card",
  "schema_version": 2,
  "stage": "complete",
  "primary_preset": "scene-card-archive",
  "blend_presets": ["paper-collage-halftone"],
  "layout": "board",
  "width": 1200,
  "height": 1600,
  "ratio": "3:4",
  "language": "zh-CN",
  "title": "",
  "subtitle": "",
  "microcopy": "",
  "source_ids": [],
  "catalog_sha256": "",
  "custom_reference": false,
  "generated_at": ""
}
```

## Validation gates

### Thumbnail gate

- 目录中的每个预设都有真实缩略图或失败占位卡；
- `style-gallery.png` 存在并可打开；
- 新会话的第一人称 `style-gallery.html`、二维 `style-gallery-accessible.html`、静态 PNG 与 `gallery-manifest.json` 存在，顺序和目录哈希一致；
- 主 HTML 提供 Three.js 桌面三维展馆、木质前厅、自动近景入场、固定正面策展位、850ms 光幕切换、侧边前后按钮、方向键、实体翻页名册、镜语室、动效减弱和技术回退；不保留自由行走、指针锁定、移动摇杆或移动端布局；
- 主展馆入场后保持相机、墙面和灯光稳定，只在固定策展位逐层显影下一幅，并为每幅作品提供独立标题、简介和小号风格注记；
- 墙签、展品清单、细看层和技术回退中的标题均单行完整显示；细看层为左侧策展信息、右侧放大展品和虚化展厅背景；画框拖动具有离墙深度与回弹；
- HTML 不加载外部运行时资源；所有墙面 WebP 可打开且数量与目录一致；
- 所有缩略图使用同一主图和同一证据矩阵；
- 不存在 `final/editorial-card.png`；
- 会话停在 `awaiting-selection`。

### Final gate

- `selection.lock.json` 存在且目录哈希匹配；
- 选择编号与 `selection-map.json`、预设 ID 一致；
- `primary_preset` 和 blend 均在目录中；
- 每幅内部合成 PNG/JPG 尺寸与各自 metadata 一致；取件包还必须包含可校验的 `master.png`、1800×2400 的 `xhs-3x4.jpg`、展签、生成记录与自动质检记录；
- 取件网页、取件单、收藏 manifest 与 ZIP 完整，项目顺序与选择锁一致；
- 图层、提示词、素材清单和 QA 报告存在；
- 原始输入文件未被覆盖，源图哈希与会话记录一致；
- 人工视觉检查记录为 PASS。

## Delivery rules

- 默认成品为 1200×1600；用户指定比例时记录实际尺寸和比例。
- 使用 PNG 交付无损成品，JPG 作为兼容预览。
- 精确文字只在后期合成，不依赖生成图中的文字。
- 记录外部参考项目的链接和适配器，但不打包受限参考文件。
- 用户更换标题、比例、文案或留白时优先重跑合成脚本，不重复生成设计素材。
- 手机照片按 EXIF 方向转正后分析和合成，但 `sources/` 中始终保存未改写的原文件副本与哈希。
