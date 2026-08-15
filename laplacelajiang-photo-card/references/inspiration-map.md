# Inspiration map

本文件记录公开项目对预设设计的启发，只提炼视觉方法和工作流原则，不复制原项目的提示词、示例图、品牌资产或实现代码。

现在注册表中的每个参考项目都有一个对应的“参考结果预设”。它描述的是用户最终可以选择的成品形态，而不是外部项目的原始素材复用。

| 公开参考 | 提炼到本 skill 的方向 |
| --- | --- |
| [travel-photo-abstraction](https://github.com/Evianis/travel-photo-abstraction) | 从照片证据提取形状、色彩、方向、层次和负空间，生成稀疏抽象面板；保留原图的空间关系。 |
| [photo-abstract-editorial](https://github.com/ZzzLc0405/photo-abstract-editorial) | “原照片 + 派生视觉面板 + 编辑标题”的双栏卡片结构，抽象内容必须回到照片事实。 |
| [editorial-vision-studio](https://github.com/Yu-0312/editorial-vision-studio) | 用视觉导演思路先确定构图、叙事、材质和版式，再进入生成；对应 `structured-scene-narrative`。 |
| [gbro-collage-broll](https://github.com/pyang5166/gbro-collage-broll) | 纸张、网点、切片、撕边和有限强调色的拼贴语言；在本 skill 中只保留静帧卡片部分。 |
| [Infographic](https://github.com/antvis/Infographic) | 让信息结构、图形关系和阅读层级服务于真实内容；对应 `infographic-editorial`。 |
| [AI-Visual-Prompt-Cookbook](https://github.com/VigoZhao/AI-Visual-Prompt-Cookbook) | 预设注册表、机器可读字段、缩略图画廊和“先选方向、后生成细节”的产品化方式。 |
| [scene-card-studio](https://github.com/swping999/scene-card-studio) | 场景卡片的模块化信息层级、主图—细节—标签关系和可编辑版式。 |
| [photo-revival](https://github.com/dacnay816y62-hub/photo-revival) | 白纸、手绘线条、低刺激色块和不确定细节不乱补的诗性复原方向。 |
| [xianxia-visual-director](https://github.com/liyue-aigc/xianxia-visual-director) | 绢本、墨色、东方留白和氛围层次；在本 skill 中避免扩展成未经证实的历史或神话内容。 |
| [video-shotcraft](https://github.com/Vincentwei1021/video-shotcraft) | 镜头配方、构图意图和风格规则的结构化表达；只吸收其“规则卡”思路，不生成视频。 |
| [hbg-classical-poem-silk-video](https://github.com/Mr-funny/hbg-classical-poem-silk-video) | 绢纸、诗性题签、墨色远景和留白的静帧化表达。 |
| [story-to-handdrawn-video](https://github.com/gnipbao/story-to-handdrawn-video) | 多图输入时用分格、旁注和动作顺序形成手绘日记；单图不虚构前后情节。 |
| [one-frame-one-metaphor](https://github.com/estherliu-lab/one-frame-one-metaphor) | 将一项可见事实压缩为单一视觉隐喻和单帧焦点。当前链接无法访问且许可未核验，只注册为隔离的兼容适配器，不原生调用。 |
| [gc-minimal-zine-poster](https://github.com/LiamGvchi/gc-minimal-zine-poster) | 70%–90% 负空间、单一小型视觉锚点、一处高纯度强调色、旧纸与复印／孔版印刷缺陷；原生路由对应 `gc-minimal-zine-poster-v0-3`。 |
| [Kage](https://mengto.github.io/kage/) | 只提炼全屏入口、章节化滚动、巨型编号、暗场聚焦、持续进度和局部放大的展览语法；不复制其京都内容、照片、文案、字体、品牌符号、Three.js 场景或实现代码。 |
| [MengTo Skills](https://github.com/MengTo/skills) | 采用可移植 demo、明确默认值与限制、验收标准驱动的组织方式；仓库为 MIT，但本 skill 的展览代码保持独立实现。 |

## 使用边界

- 参考项目只作为方向来源，不能替代用户对某一张照片的实际选择。
- 有来源链接不等于本机安装；只有 `check_native_routes.py` 报告 `native-available`，并且用户明确要求原生流程时，才调用对应 skill。
- 原生调用还要遵守该项目自己的许可证和商业使用条件；无法确认时使用本 skill 的兼容适配器。
- 预设的缩略图必须使用同一张用户照片，便于比较风格而不是比较素材。
- 任何抽象图形、标签、数据或故事，都要能在证据矩阵中找到来源；无法确认的内容改为氛围性表达或留白。
