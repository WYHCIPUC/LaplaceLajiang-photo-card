# LaplaceLajiang Photo Card

一个面向 Codex 的照片美化与风格化 Skill。它先让同一张照片试演 24 种视觉语言，再把候选作品挂进一座温暖、离线的 Three.js 私人影像展；用户看展、翻阅名册并收藏 1–6 幅后，系统才进入高清制作与取件打包。

当前稳定版：**4.0.0**。

## 两种使用方式

### 廿四境 · 私人影像展

- 24 个方向：10 个原生预设与 14 个参考结果适配器。
- 真实 Three.js 桌面展馆：PBR 白橡木地板、象牙灰泥墙、深红木／旧黄铜画框、2700K 展灯与冷色暮光。
- 点击黄铜门把入场后自动到达最佳观赏位；视角始终正对墙面。
- 同墙作品使用约 850ms 光幕平滑切换，建筑与相机不整体晃动。
- 点击作品可完整细看、按住比较母片、细节镜缩放／平移、拖动画框感受摆动与离墙深度。
- 亚麻硬壳展品名册：6 个章节、每个双页 4 幅、真实翻页并可直达墙上作品。
- 镜语室：24 式基础／进阶配方与一键复制。
- 收藏袋通过 localhost 状态桥写入真实选择锁；页面不伪造高清生成进度。
- 每幅选中作品交付高清母版、1800×2400 小红书版、展签、生成记录与质检记录。
- 自动 GPU 质量判断，并提供流畅／均衡／精细三档手动覆盖。

展厅仅面向桌面：最低 1366×768，推荐 1920×1080；支持 2560×1440 与超宽屏，不提供移动端布局。

### 镜语廿四式 · 风格配方馆

面向未安装 Codex 的使用者，可把相同的 24 个方向导出为一个完全自包含的离线 HTML：

- 24 张同源样图；
- 通用、豆包、Kimi、千问四套平台表达；
- 保真优先、平衡推荐、强烈实验三档；
- 双参考强风格与每式专属修复词；
- 内嵌教程、隐私、授权和平台能力边界；
- 无外部字体、脚本、图片或网络依赖。

## 安装

将 `laplacelajiang-photo-card` 文件夹复制到 Codex skills 目录：

```powershell
Copy-Item -Recurse .\laplacelajiang-photo-card "$env:USERPROFILE\.codex\skills\laplacelajiang-photo-card"
```

重新打开 Codex 后运行：

```powershell
python "$env:USERPROFILE\.codex\skills\laplacelajiang-photo-card\scripts\photo_card.py" doctor
python "$env:USERPROFILE\.codex\skills\laplacelajiang-photo-card\scripts\photo_card.py" self-test
```

依赖：Windows、Python 3.10+、Pillow、Codex 或兼容 Agent Skills 的运行环境。真实风格图生成仍需可用的图像生成能力。

## 在 Codex 中使用

上传照片并说：

```text
使用 $laplacelajiang-photo-card 处理这张照片，先生成完整的 24 风格私人影像展，等我收藏后再做高清图。
```

工作流：

```text
原图副本与证据矩阵
  → 24 风格缩略图
  → 三维私人影像展
  → 收藏 1–6 幅并写入选择锁
  → 逐幅高清制作
  → 取件网页、清单、哈希与 ZIP
```

统一命令入口：

```powershell
python laplacelajiang-photo-card/scripts/photo_card.py --help
```

主要命令包括 `doctor`、`start`、`status`、`gallery`、`serve`、`select`、`package`、`consumer-pack`、`consumer-page`、`migrate`、`resume`、`validate` 与 `self-test`。

## 设计门禁

- 不覆盖用户原图，先保存副本、尺寸、方向与哈希。
- 24 个预设全部进入缩略图试演；失败项保留明确状态，不静默跳过。
- 没有 `selection.lock.json` 时禁止高清生成。
- 照片区优先使用原始像素；精确文字由确定性脚本排版。
- 最终包必须通过机器校验和人工视觉检查。
- 不复制参考项目的示例图、私有提示词、品牌资产或受限代码。

详细规则见 [`laplacelajiang-photo-card/SKILL.md`](laplacelajiang-photo-card/SKILL.md)。

## 第三方与许可

本仓库自有代码采用 MIT License。展厅离线运行时包含 Three.js、GSAP 与 ambientCG PBR 贴图，具体版本、来源与许可见 [`THIRD-PARTY-NOTICES.md`](laplacelajiang-photo-card/assets/exhibition/THIRD-PARTY-NOTICES.md)。参考项目仍受各自许可证约束；本 Skill 默认只实现独立的结果形态适配器，不打包外部仓库资产。

## 验证

```powershell
python laplacelajiang-photo-card/scripts/check_preset_catalog.py laplacelajiang-photo-card
python laplacelajiang-photo-card/scripts/photo_card.py self-test
```

自检覆盖会话状态、24 风格目录、画廊合同、选择门禁、高清合成、取件打包、单页提示词商品与全部 24 种版式。
