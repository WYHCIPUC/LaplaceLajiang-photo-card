"""Build a no-Codex consumer prompt product from the 24-preset catalog."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import zipfile
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PLATFORM_NOTES = {
    "通用": (
        "请把我上传的图片作为唯一事实来源执行图生图/图片编辑，而不是只描述图片。"
        "若当前模式只能理解图片，先停止并提醒我切换到支持图片生成或图片编辑的模型/插件。"
    ),
    "豆包": (
        "请进入支持参考图的图片生成/图片编辑能力，使用上传图作为参考图。"
        "保持主体、构图和光线关系，按下述风格生成 1 张 3:4 图片。"
    ),
    "Kimi": (
        "请调用可用的创意设计类图像生成插件，并把上传图作为视觉参考。"
        "如果当前会话只有视觉理解、没有可用生图插件，请不要只返回文字描述；请明确提示我先安装或切换图像生成插件。"
    ),
    "千问": (
        "请使用支持图像编辑的千问/Qwen-Image 或万相图像编辑能力，把上传图作为输入图。"
        "执行风格迁移并生成 1 张 3:4 图片。"
    ),
}

COMMON = (
    "完整保留原图中可识别主体的身份、面部特征、姿态、数量、主要轮廓、前后景关系、遮挡、视角与光照方向；"
    "颜色优先取自原图。允许改变媒介、纸张、线条、拼贴、排版与抽象程度，但不要无依据新增或删除人物、物体、地标、品牌、文字、日期、数字、事件或文化故事。"
    "原图为横图或方图时，用留白、衬纸、边缘延展或设计面板适配 3:4，不要强行裁掉主体。"
    "画面中不要生成可读文字、乱码、签名、Logo、水印和界面元素；为后期文字保留干净区域。"
    "质感精致、层次清晰、适合社交媒体保存与打印，输出单张成图。"
)

STYLE_TUNING = {
    "fashion-sketch": "暖白艺术纸，大面积留白，松弛的石墨与黑色墨线，只保留一个来自原图的强调色；呈现高级时装手稿与编辑摄影结合的照片卡。",
    "retro-travel-collage": "奶油旧纸、低饱和复古配色、原图裁片、克制的撕边和几何纸块，形成有旅行刊物气质的完整拼贴。",
    "sparse-visual-abstraction": "保留一块清晰可辨的原照片区域，旁侧使用稀疏抽象面板映射轮廓、方向、遮挡、深度与负空间；极简且有研究感。",
    "editorial-memory-panel": "安静的杂志编辑构图，主照片配柔和记忆色面板、少量几何符号与留白，像被精心保存的一页视觉回忆。",
    "structured-scene-narrative": "模块化场景档案网格，一张主图配真实来源的局部裁片、观察标记和清晰阅读顺序；不添加虚构故事。",
    "paper-collage-halftone": "旧纸、丝网印刷网点、粗粝剪贴层、撕边、黑色图形记号与一个高饱和强调色，形成静态半调拼贴。",
    "infographic-editorial": "洁净的信息图编辑风格，用定性箭头、轮廓线、景深色带和观察标记组织原图可见关系，不生成数字或统计结论。",
    "poetic-white-paper": "近白纸面、细腻石墨或蜡笔轮廓、少量低饱和色，保留不确定细节的空白，呈现轻盈诗性的手绘复原。",
    "eastern-silk-cinema": "绢丝纤维、墨洗景深、克制的青瓷色与朱砂色、东方留白和电影静帧氛围；只改变媒介，不添加仙侠角色或建筑。",
    "handdrawn-diary-storyboard": "1–3 个手绘日记分镜，暖纸底、铅笔淡彩、从原图提取的动作线与箭头，亲密自然，不生成可读手写文字。",
    "photo-abstraction-study": "保留原图剪影、重复、空间节奏、视点与负空间，用几何平面、透明色块和切片地平线形成照片抽象研究图。",
    "photo-memory-editorial": "竖版照片记忆编辑页，主照片保持清晰，搭配源图衍生的抽象记忆面板、纸边与安静的档案层次。",
    "vision-director-board": "单页视觉导演方案板：一张英雄主图、若干真实局部裁片、材质测试、构图选项与统一配色；不生成可读说明文字。",
    "halftone-broll-frame": "动势明确的静态 B-roll 关键画面，网点纸张拼贴、粗糙轮廓、层叠剪贴、模拟胶片颗粒与清晰视觉轴线。",
    "data-story-poster": "把画面可见的高度、方向、层次、重复与空间关系组织成海报化信息结构；使用抽象条形和径向图形，但不出现伪数据。",
    "prompt-styleboard": "同一照片的多样式小样矩阵，包含主画面、局部裁片、配色条与材质样本；所有小样保持同一主体与构图证据。",
    "scene-card-archive": "可编辑感场景卡档案：主照片、真实细节裁片、观察标签安全区与克制叙事层级；像专业影视场景归档。",
    "revival-sketch-sheet": "白纸复原手绘图页，用石墨轮廓、水彩修复层和少量保留的照片碎片呈现被珍惜的视觉档案；未知细节保持模糊。",
    "celestial-xianxia-still": "在真实主体和真实空间上叠加东方天境氛围：矿物色、丝绢与墨雾、宏阔景深；不新增人物、宫殿、山岳或神话物件。",
    "shot-recipe-keyframe": "专业电影镜头配方关键帧：一张建立镜头配若干真实细节帧，突出景别、主体位置、光线方向与运动暗示，不生成文字。",
    "classical-poem-silk-poster": "竖版绢本诗意海报，无诗文：细密丝纹、墨色景深、克制矿物色、安静题签留白与朱砂视觉锚点。",
    "handdrawn-diary-page": "单页亲密手绘日记，彩铅、石墨和透明水彩重绘原图关系，可有胶带角和不可读的记号笔触，保持自然纸影。",
    "one-frame-metaphor": "把原图最鲜明的一个视觉关系转化为单一、清晰、可感知的隐喻；保持事实和主体，使用大留白与克制编辑框架，不增加新物体。",
    "minimal-zine-poster": "高级极简 Zine 海报：70%–90% 暖纸留白，一处小型原图视觉锚点，一个高纯度强调色，轻微复印/孔版印刷缺陷与果断不对称。",
}

PLATFORM_GUIDANCE = {
    "通用": (
        "把上传图片绑定为唯一事实来源，并在支持参考图的图生图／图片编辑模式中执行。"
        "参考图不是可选灵感：主体身份、数量、姿态、关键物件和空间关系必须来自它。"
        "如果当前模式只能看图或写文字，停止生成并明确提醒切换到图片编辑能力。"
    ),
    "豆包": (
        "在豆包中使用支持参考图的图片生成／图片编辑入口，把上传图片设为主参考图。"
        "不要让自动扩写把任务改成重新创作新场景；优先执行高保真图生图，完整传递下面的分层要求。"
    ),
    "Kimi": (
        "调用可实际输出图片的创意设计／图像生成插件，并把上传图片连同以下完整提示词一并传入，"
        "不要压缩成一句风格描述。如果当前会话只有视觉理解能力，停止并提醒先切换可生图插件。"
    ),
    "千问": (
        "使用支持参考图编辑的千问／Qwen-Image 或万相图像编辑入口，把上传图片设为输入图。"
        "采用高保真编辑而不是纯文本生图；如提示词自动改写会添加新场景，应以本提示中的事实锁定和禁止项为最高优先级。"
    ),
}

INTENSITY_GUIDANCE = {
    "保真优先": (
        "原图识别度高于风格强度。主主体、人物面部、手部、姿态、服装、建筑和关键物件尽量保持照片级真实；"
        "风格主要作用于纸张、边缘、背景简化、版面组织和次级装饰。适合人物、纪念照和不可重画的主体。"
    ),
    "平衡推荐": (
        "原图事实与视觉风格同等重要。允许整体媒介转换、局部抽象和版式重组，"
        "但主体身份、数量、姿态、主轮廓、视觉焦点、相机视角、遮挡和前后景关系必须一眼对应原图。"
    ),
    "强烈实验": (
        "允许更大胆地改变媒介、比例节奏、负空间、拼贴层次和抽象程度，形成作品感；"
        "仍禁止新增角色、道具、建筑、文字或故事，并保留足够的主体锚点，使人能够明确认出同一照片。"
    ),
}

SOURCE_ANALYSIS = (
    "先在内部读取参考图，不要输出分析过程。识别并锁定：①人物／动物／建筑／物体的数量与身份锚点；"
    "②脸部、手部、姿态、服装和关键物件；③主体在画面中的位置、朝向、尺度、遮挡和前中后景；"
    "④相机高度、透视、地平线、裁切边界；⑤主光方向、色温、最亮区、最暗区与 3–5 个主色；"
    "⑥最有辨识度的一处视觉关系。模糊或被遮挡的内容保持模糊／遮挡，不要猜测补全。"
)

FACT_LOCK = (
    "不可无依据新增、删除、替换或复制人物、动物、建筑、植物、交通工具、标志物和道具；"
    "不可改变人物身份、年龄感、五官比例、发型、身体比例、动作、视线和服装结构；"
    "不可交换左右、改变天气／时间、移动地平线、制造第二光源或改写原图事件。"
)

EXPERIMENTAL_FACT_LOCK = (
    "锁定主体身份、数量、关键脸部／手部特征、主要轮廓、核心物件和最有辨识度的视觉关系；"
    "禁止新增角色、建筑、道具、文字和故事。允许为了拼贴、抽象或海报构图，对同一原图的局部进行裁切、分层、"
    "缩放、错位、重排和媒介转换，但所有片段必须同源，不得复制出第二个主体，也不得改变原事件含义。"
)

OUTPUT_QUALITY = (
    "输出竖版 3:4 单张成图。横图或方图用真实留白、衬纸、边缘延展、局部裁片或设计面板适配，"
    "不得强裁脸、手、脚、建筑主体和视觉焦点。画面要有明确的主焦点、次级信息与安静区；"
    "材质必须有微观纹理、厚度、边缘、接触阴影和统一光向，不能只是平涂色块或全局滤镜。"
    "焦点处精细，次要区域有控制地简化；适合高清保存、社交媒体展示与打印。"
)

GLOBAL_AVOID = (
    "不要生成可读文字、乱码、字母、数字、日期、签名、印章内容、品牌、Logo、水印、界面按钮或提示词；"
    "不要出现重复脸、额外肢体、融合手指、扭曲建筑、漂浮物、塑料质感、过度磨皮、HDR 光晕、"
    "全图统一滤镜、廉价模板、随机装饰、无来源文化符号或与原图无关的故事。"
)

STYLE_SPECS_PATH = Path(__file__).with_name("consumer_prompt_specs.json")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def fit_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    source = image.convert("RGB")
    ratio = max(size[0] / source.width, size[1] / source.height)
    resized = source.resize((round(source.width * ratio), round(source.height * ratio)), Image.Resampling.LANCZOS)
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1]))


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, width: int) -> list[str]:
    lines, current = [], ""
    for char in text:
        candidate = current + char
        if draw.textlength(candidate, font=fnt) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def make_cover(path: Path, count: int) -> None:
    canvas = Image.new("RGB", (1600, 1200), "#EDE7DC")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1600, 48), fill="#542D25")
    draw.text((92, 92), "LAPLACELAJIANG", font=font(28, True), fill="#7E4334")
    draw.text((92, 165), "照片风格提示词商品包", font=font(78, True), fill="#251D18")
    draw.text((96, 285), "无需 Codex · 24 风格 · 4 平台 · 3 档强度", font=font(31), fill="#725E50")
    draw.text((96, 410), str(count), font=font(210, True), fill="#B8543F")
    draw.text((390, 468), "种视觉风格", font=font(54, True), fill="#251D18")
    draw.text((100, 692), "豆包  /  Kimi  /  千问  /  其他支持图片编辑的平台", font=font(30, True), fill="#49372D")
    for index, label in enumerate(("456 组可复制词", "双参考强风格", "24 张样图", "离线复制页", "教程与修正词")):
        x = 96 + (index % 3) * 470
        y = 830 + (index // 3) * 120
        draw.rounded_rectangle((x, y, x + 410, y + 76), radius=16, outline="#BFA995", width=2, fill="#F8F3EA")
        draw.text((x + 28, y + 20), label, font=font(24, True), fill="#5C3A2C")
    canvas.save(path, quality=94)


def make_style_card(example: Path, output: Path, number: int, zh: str, en: str) -> None:
    source = Image.open(example)
    canvas = Image.new("RGB", (1200, 1600), "#F2EDE4")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 1200, 26), fill="#60372D")
    artwork = fit_cover(source, (940, 1120))
    canvas.paste(artwork, (130, 105))
    draw.rectangle((130, 105, 1070, 1225), outline="#482923", width=14)
    draw.text((96, 1260), f"{number:02d}", font=font(58, True), fill="#B4563E")
    draw.text((220, 1255), zh, font=font(45, True), fill="#271E19")
    draw.text((222, 1323), en.upper(), font=font(20, True), fill="#806A5B")
    description = "上传自己的图片，复制同编号提示词即可尝试。实际结果会随平台、模型版本与原图变化。"
    y = 1390
    for line in wrap(draw, description, font(24), 920)[:3]:
        draw.text((220, y), line, font=font(24), fill="#66574C")
        y += 38
    canvas.save(output, quality=94)


def prompt_for(platform: str, intensity: str, spec: dict[str, str]) -> str:
    if intensity == "强烈实验":
        return f"""【强风格重构｜只输出最终图像】
{PLATFORM_GUIDANCE[platform]}
这不是修图、调色、滤镜或在原照片上加边框。不要保留原照片的像素外观；请把它只当作内容证据，从空白画布重新制作一张竖版 3:4 作品。

【必须做成的成品】
{spec['concept']}
严格执行：{spec['recipe']}
画面主要区域必须呈现这些真实媒介：{spec['material']}
色彩与光线：{spec['color_light']}
关键细节：{spec['detail']}

【只保留这些原图证据】
主体身份与数量、关键脸部／手部特征、主要轮廓、核心物件，以及最有辨识度的一处视觉关系。允许裁切、分层、缩放、错位、重排和彻底媒介转换；所有片段必须来自同一原图，不复制第二个主体，不改变事件含义。

【失败条件】
若仍像普通照片，或只加了调色、颗粒、纸边、画框，视为失败并重新制作。特别避免：{spec['avoid']}
禁止任何可读文字、乱码、字母、数字、标题、标签、签名、印章内容、Logo、水印、分析板、步骤页、色卡说明、软件界面和前后对比。只输出 1 张无文字的完整作品。"""
    fact_lock = EXPERIMENTAL_FACT_LOCK if intensity == "强烈实验" else FACT_LOCK
    return f"""【只输出最终图像】
{PLATFORM_GUIDANCE[platform]}
直接制作一张完整的竖版 3:4 成品，不输出分析板、步骤页、教程、色卡说明、参数、前后对比或任何文字。

【风格硬指标】
视觉方向：{spec['concept']}
成品配方：{spec['recipe']}
构图设计：{spec['composition']}
媒介与材质：{spec['material']}
色彩与光线：{spec['color_light']}
细节层级：{spec['detail']}
版式、媒介、材质三项必须作用于主画面并清楚可见，不能退化成普通全幅照片加轻微调色、颗粒、纸边或滤镜。

【参考图绑定】
只在内部读取参考图，不展示读取过程。{SOURCE_ANALYSIS}
{fact_lock}

【风格强度｜{intensity}】
{INTENSITY_GUIDANCE[intensity]}

【成片质量】
{OUTPUT_QUALITY}

【本风格特别避免】
{spec['avoid']}

【全局禁止项】
{GLOBAL_AVOID}

【最终成品要求】
一眼能认出本风格，一眼能看出不是普通滤镜，同时一眼能确认主体来自同一张参考图。现在只生成 1 张完整成图。"""


def repair_prompts(spec: dict[str, str]) -> dict[str, str]:
    return {
        "风格强化重试": (
            "继续使用刚才同一张参考图，丢弃上一张结果并重新生成单幅竖版 3:4 最终作品。上一张失败的原因是风格变化不够，"
            "仍像普通照片或滤镜。不要解释、不要展示过程、不要生成分析板和文字。必须明显执行这条成品配方："
            f"{spec['recipe']} 材质必须真实可见：{spec['material']} 主体仍与参考图明确对应，但版式与媒介必须真正改变。"
        ),
        "去文字修复": (
            "只修复刚才生成的图：删除画面内全部可读文字、乱码、字母、数字、日期、标题、标签、签名、印章内容、Logo 和水印；"
            "用原有纸张、绢本、色块或留白自然补齐，不改变主体、构图、颜色、材质和其他风格效果。"
            f"继续保持当前风格的核心方向：{spec['concept']} 只输出无文字的完整成图。"
        ),
        "主体保真修复": (
            "继续使用同一参考图重新生成：严格恢复参考图中的主体身份、数量、脸部、手部、姿态、服装、关键物件、左右方向、"
            "地平线、遮挡和前后景；不要新增或删除内容。保留已经确定的风格与版式，并按这条配方重新落实："
            f"{spec['recipe']} 只输出单幅完整成图。"
        ),
    }


def dual_reference_prompt(platform: str, spec: dict[str, str]) -> str:
    return f"""【双参考图强风格模式｜只输出最终图像】
{PLATFORM_GUIDANCE[platform]}
本次同时上传两张图：图 1 是需要处理的用户原图，图 2 是本商品包内同编号的纯风格参考图。

内容只取图 1：主体身份、数量、脸部、手部、姿态、服装、建筑、关键物件、光线和最有辨识度的关系都来自图 1。
风格只取图 2：学习它的版式组织、留白比例、媒介转换、纸张／绢本／油墨／网点／线条、色彩节奏、材质层次和完成度。
绝不把图 2 中的人物、建筑、物件、文字、标志、构图内容或故事复制进成片；图 2 只提供视觉语法。

目标成品：{spec['concept']}
必须执行的重构动作：{spec['recipe']}
真实材质：{spec['material']}
色彩与光线：{spec['color_light']}
细节层级：{spec['detail']}

如果结果仍像图 1 的普通照片或滤镜，说明没有正确使用图 2 的风格，请重新生成并显著提高图 2 在版式、媒介和材质上的影响；如果结果复制了图 2 的内容，则降低内容影响，只保留视觉语法。
特别避免：{spec['avoid']}
禁止可读文字、乱码、字母、数字、日期、标题、标签、签名、印章内容、Logo、水印、分析板、步骤页、色卡说明、软件界面和前后对比。只输出一张竖版 3:4 无文字完整成图。"""


def validate_prompt_records(records: list[dict]) -> dict:
    expected_platforms = set(PLATFORM_GUIDANCE)
    expected_intensities = set(INTENSITY_GUIDANCE)
    lengths: list[int] = []
    prompt_hashes: set[str] = set()
    dual_hashes: set[str] = set()
    repair_hashes: set[str] = set()
    for record in records:
        if set(record["prompts"]) != expected_platforms:
            raise SystemExit(f"platform mismatch: {record['id']}")
        for platform, intensity_map in record["prompts"].items():
            if set(intensity_map) != expected_intensities:
                raise SystemExit(f"intensity mismatch: {record['id']} / {platform}")
            for intensity, prompt in intensity_map.items():
                markers = (
                    ("必须做成的成品", "严格执行", "真实媒介", "色彩与光线", "失败条件")
                    if intensity == "强烈实验"
                    else ("成品配方", "构图设计", "媒介与材质", "色彩与光线", "细节层级", "全局禁止项")
                )
                missing = [marker for marker in markers if marker not in prompt]
                if missing:
                    raise SystemExit(f"prompt missing {missing}: {record['id']} / {platform} / {intensity}")
                minimum = 650 if intensity == "强烈实验" else 1000
                if len(prompt) < minimum:
                    raise SystemExit(f"prompt too short ({len(prompt)}): {record['id']} / {platform} / {intensity}")
                lengths.append(len(prompt))
                prompt_hashes.add(hashlib.sha256(prompt.encode("utf-8")).hexdigest())
        if set(record["repairs"]) != {"风格强化重试", "去文字修复", "主体保真修复"}:
            raise SystemExit(f"repair prompt mismatch: {record['id']}")
        for prompt in record["repairs"].values():
            repair_hashes.add(hashlib.sha256(prompt.encode("utf-8")).hexdigest())
        if set(record["dual_prompts"]) != expected_platforms:
            raise SystemExit(f"dual-reference platform mismatch: {record['id']}")
        for prompt in record["dual_prompts"].values():
            if "内容只取图 1" not in prompt or "风格只取图 2" not in prompt:
                raise SystemExit(f"dual-reference binding missing: {record['id']}")
            dual_hashes.add(hashlib.sha256(prompt.encode("utf-8")).hexdigest())
    expected_count = len(records) * len(expected_platforms) * len(expected_intensities)
    if len(prompt_hashes) != expected_count:
        raise SystemExit(f"duplicate prompts: expected {expected_count}, unique {len(prompt_hashes)}")
    expected_repairs = len(records) * 3
    if len(repair_hashes) != expected_repairs:
        raise SystemExit(f"duplicate repair prompts: expected {expected_repairs}, unique {len(repair_hashes)}")
    expected_dual = len(records) * len(expected_platforms)
    if len(dual_hashes) != expected_dual:
        raise SystemExit(f"duplicate dual-reference prompts: expected {expected_dual}, unique {len(dual_hashes)}")
    return {
        "styles": len(records),
        "platforms": len(expected_platforms),
        "intensities": len(expected_intensities),
        "variants": expected_count,
        "min_chars": min(lengths),
        "max_chars": max(lengths),
        "avg_chars": round(sum(lengths) / len(lengths)),
        "unique_prompts": len(prompt_hashes),
        "repair_prompts": expected_repairs,
        "dual_prompts": expected_dual,
        "unique_repairs": len(repair_hashes),
        "unique_dual": len(dual_hashes),
        "total_copyable": expected_count + expected_dual + expected_repairs,
    }


def build_html(records: list[dict], output: Path) -> None:
    data = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    output.write_text(f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LaplaceLajiang 24 种照片风格提示词</title><style>
:root{{--paper:#f0e9dd;--card:#fffaf1;--ink:#261d18;--muted:#756357;--accent:#a94f39;--line:#d2c1ae}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei",system-ui,sans-serif}}
header{{padding:56px clamp(20px,6vw,96px) 32px;border-top:10px solid #593329}}h1{{font-size:clamp(36px,7vw,92px);margin:8px 0 12px;letter-spacing:-.04em}}header p{{color:var(--muted);font-size:18px}}
.bar{{position:sticky;top:0;z-index:10;background:#f0e9ddee;backdrop-filter:blur(14px);padding:14px clamp(20px,6vw,96px);border-block:1px solid var(--line);display:flex;gap:10px;flex-wrap:wrap}}
button,select{{border:1px solid #a98d79;background:#fff9ef;color:var(--ink);border-radius:999px;padding:11px 17px;font:inherit;cursor:pointer}}button:hover{{background:#5b342a;color:#fff}}
main{{padding:34px clamp(20px,6vw,96px) 80px;display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:26px}}
article{{background:var(--card);border:1px solid var(--line);box-shadow:0 18px 46px #68473518;padding:18px;border-radius:22px}}img{{width:100%;aspect-ratio:3/4;object-fit:cover;border:9px solid #5a3129;background:#eadfce}}
h2{{font-size:24px;margin:18px 0 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}small{{color:var(--muted)}}textarea{{width:100%;height:240px;margin-top:16px;padding:14px;border:1px solid var(--line);background:#fbf7ef;resize:vertical;line-height:1.7;font:14px/1.7 "Microsoft YaHei",sans-serif}}
.actions{{display:flex;justify-content:space-between;align-items:center;margin-top:12px}}.num{{color:var(--accent);font-weight:800}}footer{{padding:30px 6vw 60px;color:var(--muted);border-top:1px solid var(--line)}}
</style></head><body><header><small>LAPLACELAJIANG · CONSUMER EDITION</small><h1>24 种照片风格提示词</h1><p>无需安装 Codex。上传自己的图片，选择平台，复制提示词，在支持图片生成／图片编辑的模式中使用。</p><p>人物／纪念照先用“保真优先”，日常照片先用“平衡推荐”，风景／建筑／静物想要明显变化可直接用“强烈实验”。</p></header>
<div class="bar"><label>平台 <select id="platform"><option>通用</option><option>豆包</option><option>Kimi</option><option>千问</option></select></label><label>风格强度 <select id="intensity"><option>保真优先</option><option selected>平衡推荐</option><option>强烈实验</option></select></label><button id="copyAll">复制当前组合全部提示词</button><span id="status"></span></div><main id="grid"></main>
<footer>提示词与样图用于说明视觉方向；不同平台、模型版本、账号权限、原图质量会造成结果差异。请勿上传无权使用的图片或敏感个人资料。</footer>
<script>const DATA={data};const grid=document.querySelector('#grid'),platform=document.querySelector('#platform'),intensity=document.querySelector('#intensity'),status=document.querySelector('#status');const current=x=>x.prompts[platform.value][intensity.value];function legacyCopy(value){{const box=document.createElement('textarea');box.value=value;box.style.position='fixed';box.style.opacity='0';document.body.appendChild(box);box.select();document.execCommand('copy');box.remove();return Promise.resolve()}}function copyText(value){{return navigator.clipboard&&navigator.clipboard.writeText?navigator.clipboard.writeText(value).catch(()=>legacyCopy(value)):legacyCopy(value)}}function render(){{grid.innerHTML=DATA.map(x=>`<article><img src="样图示例/${{x.file}}" alt="${{x.number}} ${{x.zh}}"><h2><span class="num">${{x.number}}</span> ${{x.zh}}</h2><small>${{x.en}} · ${{intensity.value}}</small><textarea readonly>${{current(x)}}</textarea><div class="actions"><span>3:4 · 单张成图</span><button data-copy="${{x.number}}">复制主提示词</button></div><div class="actions"><button data-dual="${{x.number}}">双参考强风格</button><button data-repair="${{x.number}}|风格强化重试">风格不够</button><button data-repair="${{x.number}}|去文字修复">出现文字</button><button data-repair="${{x.number}}|主体保真修复">主体跑偏</button></div></article>`).join('');grid.querySelectorAll('[data-copy]').forEach(b=>b.onclick=()=>{{const x=DATA.find(v=>v.number===b.dataset.copy);copyText(current(x)).then(()=>{{b.textContent='已复制';setTimeout(()=>b.textContent='复制主提示词',900)}})}});grid.querySelectorAll('[data-dual]').forEach(b=>b.onclick=()=>{{const x=DATA.find(v=>v.number===b.dataset.dual);copyText(x.dual_prompts[platform.value]).then(()=>{{b.textContent='已复制，请同时上传原图和本编号样图';setTimeout(()=>b.textContent='双参考强风格',1600)}})}});grid.querySelectorAll('[data-repair]').forEach(b=>b.onclick=()=>{{const [number,name]=b.dataset.repair.split('|'),x=DATA.find(v=>v.number===number);copyText(x.repairs[name]).then(()=>{{const old=b.textContent;b.textContent='已复制';setTimeout(()=>b.textContent=old,900)}})}})}}platform.onchange=render;intensity.onchange=render;document.querySelector('#copyAll').onclick=()=>{{copyText(DATA.map(x=>`#${{x.number}} ${{x.zh}}\\n${{current(x)}}`).join('\\n\\n====================\\n\\n')).then(()=>{{status.textContent=`已复制 ${{platform.value}} · ${{intensity.value}} 全部提示词`;setTimeout(()=>status.textContent='',1600)}})}};render();</script></body></html>""", encoding="utf-8")


def build(args: argparse.Namespace) -> None:
    catalog = load_json(args.catalog)
    style_specs = load_json(STYLE_SPECS_PATH)
    items = catalog["native_presets"] + catalog["reference_result_presets"]
    if len(items) != 24:
        raise SystemExit(f"expected 24 presets, found {len(items)}")
    item_ids = {item["id"] for item in items}
    if set(style_specs) != item_ids:
        missing = sorted(item_ids - set(style_specs))
        extra = sorted(set(style_specs) - item_ids)
        raise SystemExit(f"style spec mismatch; missing={missing}, extra={extra}")
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"output must be new or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    prompts_dir = output / "24种提示词"
    examples_dir = output / "样图示例"
    docs_dir = output / "使用说明"
    prompts_dir.mkdir(); examples_dir.mkdir(); docs_dir.mkdir()

    records = []
    all_markdown = ["# LaplaceLajiang 24 种照片风格提示词\n"]
    for number, item in enumerate(items, 1):
        source = args.preview_dir / f"{item['id']}.png"
        if not source.is_file():
            raise SystemExit(f"missing sample preview: {source}")
        zh = item["label"].split("/")[-1].strip()
        en = item["label"].split("/")[0].strip()
        spec = style_specs[item["id"]]
        prompts = {
            platform: {
                intensity: prompt_for(platform, intensity, spec)
                for intensity in INTENSITY_GUIDANCE
            }
            for platform in PLATFORM_GUIDANCE
        }
        dual_prompts = {platform: dual_reference_prompt(platform, spec) for platform in PLATFORM_GUIDANCE}
        file_name = f"{number:02d}-{item['id']}.jpg"
        make_style_card(source, examples_dir / file_name, number, zh, en)
        repairs = repair_prompts(spec)
        block = [f"# {number:02d} {zh} / {en}", ""]
        for platform, intensity_map in prompts.items():
            block.extend((f"## {platform}版", ""))
            for intensity, prompt in intensity_map.items():
                block.extend((f"### {intensity}", "", prompt, ""))
        block.extend(("## 双参考图强风格模式", "", "同时上传用户原图作为图 1，并上传本商品包 `样图示例` 中同编号样图作为图 2。", ""))
        for platform, dual_prompt in dual_prompts.items():
            block.extend((f"### {platform}版", "", dual_prompt, ""))
        block.extend(("## 失败后追加修复词", ""))
        for repair_name, repair_prompt in repairs.items():
            block.extend((f"### {repair_name}", "", repair_prompt, ""))
        (prompts_dir / f"{number:02d}-{item['id']}.md").write_text("\n".join(block), encoding="utf-8")
        all_markdown.extend(block)
        records.append({"number": f"{number:02d}", "id": item["id"], "zh": zh, "en": en, "file": file_name, "prompts": prompts, "dual_prompts": dual_prompts, "repairs": repairs})

    qa = validate_prompt_records(records)
    (output / "24种提示词-全集.md").write_text("\n".join(all_markdown), encoding="utf-8")
    (output / "prompts.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(args.source_image, examples_dir / "00-测试原图.jpg")
    make_cover(output / "商品封面.jpg", len(items))
    build_html(records, output / "打开我-提示词复制中心.html")

    (docs_dir / "00-提示词质量报告.md").write_text(f"""# 提示词质量报告

生成日期：{date.today().isoformat()}

- 风格：{qa['styles']} 种
- 平台适配：{qa['platforms']} 套
- 风格强度：{qa['intensities']} 档
- 可复制提示词组合：{qa['variants']} 组
- 每风格专属修复词：{qa['repair_prompts']} 组（风格强化／去文字／主体保真）
- 双参考图强风格词：{qa['dual_prompts']} 组（图 1 锁内容，图 2 取视觉语法）
- 总可复制提示词：{qa['total_copyable']} 组
- 唯一主提示词：{qa['unique_prompts']} 组
- 唯一双参考词：{qa['unique_dual']} 组
- 唯一修复词：{qa['unique_repairs']} 组
- 单条长度：{qa['min_chars']}–{qa['max_chars']} 字符，平均 {qa['avg_chars']} 字符
- 结构检查：全部包含只输出最终成图、风格专属成品配方、参考图绑定、事实锁定、构图设计、媒介材质、色彩光线、细节层级、特别避免项、全局禁止项与输出指令
- 重复检查：PASS（主提示词与修复词均无重复）

默认建议先使用“平衡推荐”。人物肖像、纪念照或不可重画主体优先用“保真优先”；风景、建筑、静物与已经测试稳定的原图可尝试“强烈实验”。
""", encoding="utf-8")

    (docs_dir / "01-三分钟使用教程.md").write_text("""# 三分钟使用教程

1. 打开豆包、Kimi、千问或其他支持图片生成／图片编辑的平台。
2. 确认当前入口能“输出图片”，不是只进行图片识别或文字问答。
3. 上传自己的原图；不要上传无权使用、含敏感信息或涉及他人隐私的图片。
4. 打开 `打开我-提示词复制中心.html`，选择平台、风格强度和喜欢的编号，复制提示词。默认先用“平衡推荐”。
5. 将完整提示词和原图放在同一条消息中发送，不要只复制“风格目标”片段。第一次先生成 1 张、使用 3:4 比例。
6. 第一张风格太弱、出现文字或主体跑偏时，直接点击对应卡片底部的“风格不够／出现文字／主体跑偏”按钮，复制该风格专属修复词并接着发送。
7. 如果平台反复只输出轻度滤镜，点击“双参考强风格”：同时上传自己的原图作为图 1、商品包中同编号样图作为图 2，再发送复制出的双参考词。
8. 满意后再请求高清版本并立即下载保存。

## 平台入口提示

- 豆包：选择带“图片生成、图生图、参考图或图片编辑”能力的入口。
- Kimi：普通视觉对话可以看懂图片，但实际出图通常需要创意设计类图像生成插件；没有插件时先安装或切换。
- 千问：选择支持图像编辑的千问/Qwen-Image 或万相模型，而不是只支持视觉理解的聊天模型。

界面、模型和额度会更新，请以平台当时显示为准。
""", encoding="utf-8")
    (docs_dir / "02-失败修正词.md").write_text("""# 失败修正词

将对应句子追加到原提示词末尾，一次只处理一个问题。

## 主体不像／人物变脸

重新生成：提高输入图参考权重。严格保持人物身份、五官比例、发型、年龄感、体型、服装轮廓、姿态和人数；只改变画面媒介与版式，不重新设计人物。

## 构图跑偏

重新生成：锁定原图相机视点、主体位置、地平线、前中后景、遮挡和光照方向；不要交换左右，不要新增场景。用留白和衬纸适配 3:4。

## 画面太乱

做减法：减少装饰元素、纸片、箭头和纹理数量，保留一个视觉焦点和大面积负空间，色彩不超过原图主色加一个强调色。

## 出现乱码／假文字

删除所有文字、字母、数字、签名、印章内容、Logo 和水印，只保留干净排版安全区。

## 平台只回复文字

当前模式可能只有图片理解能力。请停止分析，切换到支持图片生成／图像编辑的模型或插件后，再使用同一原图和提示词。

## 没有严格 3:4

重新输出为竖版 3:4；完整保留主体，用纸张留白、衬底或边缘延展补足画布，不裁掉脸、手、建筑或视觉焦点。
""", encoding="utf-8")
    (docs_dir / "03-平台能力与隐私说明.md").write_text(f"""# 平台能力与隐私说明

核对日期：{date.today().isoformat()}

- 豆包／Seedream：官方资料说明支持文本与参考图组合输入、参考生图和图像编辑；个人端具体入口随版本和权限变化。
- Kimi：官方帮助说明可上传图片；图像生成依赖创意设计类插件。普通视觉模型能理解图片，不代表必然能直接输出编辑后的图片。
- 千问／阿里云百炼：Qwen-Image 与万相的部分模型支持图片编辑和风格迁移；应选择明确标注“图像编辑”的模型。

## 重要提示

- 本商品提供提示词、操作结构和样图，不包含各平台会员、额度、API Key 或模型服务。
- 样图只说明可能的视觉方向，不承诺不同平台得到像素级相同结果。
- 平台可能保存用户上传内容。上传人物、证件、地址、聊天截图、商业机密前，请阅读平台隐私设置与服务条款。
- 商品作者无法控制平台审核、排队、限额、水印、模型更新和下载链接期限。
""", encoding="utf-8")
    (docs_dir / "04-商品授权建议.md").write_text("""# 商品授权建议（发布前请按实际经营方式确认）

建议默认授予买家：个人使用、自媒体配图和自有业务成图使用权。

建议明确禁止：转售或公开分享本提示词包、拆分提示词二次售卖、冒充原创模板库、批量上传到素材站、用商品文件训练或建立竞争性提示词产品。

提示词生成结果的权利、商用范围和平台标识要求，仍受所用平台条款、输入素材权利及当地法律约束。本文件不是法律意见；正式上架前请结合销售平台规则复核。
""", encoding="utf-8")
    (docs_dir / "05-商品详情页文案.md").write_text("""# 商品详情页文案

## 标题

24 种高级照片风格提示词｜豆包 Kimi 千问通用｜上传图片直接用

## 一句话卖点

无需安装 Codex，也不用研究复杂参数：上传自己的照片，复制对应提示词，即可尝试 24 种编辑、拼贴、手绘、东方绢本、电影静帧与极简海报方向。

## 商品包含

- 24 种风格 × 通用／豆包／Kimi／千问 × 保真／平衡／强烈三档，共 288 组完整提示词
- 每种风格另配“风格强化／去文字／主体保真”三条修复词，共 72 组
- 96 组双参考图强风格提示词：图 1 锁定内容，图 2 提供版式、材质与视觉语法
- 24 张同源样图示例与风格编号
- 可同时选择平台与风格强度的离线提示词复制中心
- 三分钟教程、保真修正词、失败排查和隐私说明
- Markdown 全集与 JSON 结构化文件

## 发货形式

数字商品 ZIP 自动／人工发货，不包含平台会员和代生成服务。

## 购买前须知

不同平台、模型版本、账号权限与原图会带来不同结果；样图用于展示视觉方向，不承诺完全复刻。Kimi 需使用可实际生成图片的创意设计插件，普通图片理解对话可能只输出文字。
""", encoding="utf-8")
    (output / "文件清单.txt").write_text("\n".join(sorted(str(p.relative_to(output)).replace("\\", "/") for p in output.rglob("*") if p.is_file())), encoding="utf-8")

    hashes = []
    for path in sorted(p for p in output.rglob("*") if p.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes.append(f"{digest}  {str(path.relative_to(output)).replace(chr(92), '/')}")
    (output / "SHA256SUMS.txt").write_text("\n".join(hashes), encoding="utf-8")

    archive = output.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(p for p in output.rglob("*") if p.is_file()):
            zf.write(path, Path(output.name) / path.relative_to(output))
    print(f"PASS: built {len(records)}-style consumer prompt pack -> {output}")
    print(f"PASS: archive -> {archive}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--catalog", type=Path, required=True)
    root.add_argument("--preview-dir", type=Path, required=True)
    root.add_argument("--source-image", type=Path, required=True)
    root.add_argument("--output", type=Path, required=True)
    return root


if __name__ == "__main__":
    build(parser().parse_args())
