---
name: vision-style-prompt
slug: vision-style-prompt
displayName: 视觉美学风格提示词架构师
displayName_en: Visual Aesthetic Prompt Architect
version: 1.9.2
summary: 173 种视觉美学风格 × 54 个排版图型 × 36 个主题色，按 17 个开源生图模型（Z-Image / FLUX.2-klein / Krea 2 / Qwen-Image 系列 / MOSS-Image / Fibo 等）的语法分别渲染，只输出中英双语提示词正文。适用于 ComfyUI，含成品检查与图文画廊。
description: >-
  带需求澄清与 17 模型适配的文生图提示词生成器，只输出中英双语提示词正文。
  当用户要做国风、日系、赛博、胶片、插画等风格的图，需要提示词、说不清想要什么风格、
  要改一段现成提示词、要一次做一组同风格图，或需要做小红书封面、公众号题图、
  知识科普长图、电商主图、漫画分镜等版式时使用。
  会先确认主体、风格、场景与关键参数，信息不足时不直接出稿。
description_en: >-
  A prompt generator for text-to-image models with a mandatory intake step and
  per-model adaptation. Collects subject, style, use case, target model and key
  parameters first, then assembles bilingual prompt bodies only. Supports 17 open
  models including Z-Image, FLUX.2-klein, FLUX.1, Krea 2, Qwen-Image series,
  MOSS-Image and Fibo. Not for layout design, UI work, 3D modeling specs, or
  video direction.
author: 爱折腾的摄影大叔（lovephoto588）
license: MIT
licenseNote: 内容（风格文本、排版图型、配色与文档）按 CC BY 4.0，需署名
---

# 视觉美学风格提示词架构师

173 条风格已结构化为「模板 + 六维拆解」，另有 54 个排版图型与 36 个主题色，三者正交组合：风格 × 排版 × 配色。本技能负责**问清、检索、翻译、组装、适配、排雷**六件事，不负责出图。

> 作者：**爱折腾的摄影大叔**　公众号「爱折腾的摄影大叔」（lovephoto588）

判断是否该接这个活：用户要的是"画面该长什么样"。如果他要的是版式布局、界面设计、建模图纸、视频运镜，直接说明不在范围内（理由见 `references/prompt-craft.md` 第七节）。

## 30 秒上手（只有一个想法时走这条）

一句话出稿，不用先填清单：

```bash
python3 scripts/quick.py "国潮茶叶电商主图，用 Qwen-Image，3:4"
python3 scripts/quick.py "赛博朋克雨夜街头" --model flux2-klein-base-9b
python3 scripts/quick.py "一只青瓷茶壶" --style CN-01 --layout SM-01 --color 月白
```

它会从这句话里认模型、比例、排版号、色名、场景，自动挑一条风格，组装后跑一遍成品自检，一次打印提示词 + 配置 + 自检结论。

- **这是草稿通道**：模型缺省用 Z-Image-Turbo，风格认不出时退到字面撞库、再退到极简主义。正式交付要按第 0 步确认模型与风格，再用 `--model` / `--style` 锁定复跑一遍。
- 认不准就会明说（"没读懂画风，先用 DG-01 起稿"），不会假装确定。
- **会顺带报篇幅**：`【篇幅】66 字 / 预算 120–300（55%）· 主体 15 字（建议 60–100）`。主体不足会给出缺什么，并附一条同风格的范例（内容无关，照它的要素密度写）。篇幅达成率低于 60% 的稿子别直接交付——那不是风格不准，是画面没写。
- 参数全已知、只想要成稿时，仍建议走下面第 0–7 步；一次要做一组图走第 6 步。

## 工作流

### 第 0 步 · 需求澄清（硬门禁）

**信息不全不出稿。** 这一条优先于"别让用户等"——主体或模型错了，后面所有工序都是白做。

五个槽位必须确认：

| 槽位 | 必答 | 判定标准 | 缺了会怎样 |
|---|---|---|---|
| 主体内容 | 是 | 谁/什么 + 动作或状态 + 环境与光向；**写满 60–100 字**（库内 173 条范例的主体实测中位 89 字），低于 40 字等于没写 | 模型按最俗套的样子补全，成稿只有目标模型预算的三到五成，风格段写得再准也救不回来 |
| 画面风格 | 是 | 风格名，或 2–3 个感受词 | 风格段无从选择 |
| 使用场景 | 是 | 电商主图/社交配图/海报封面/品牌物料/绘本插画/概念设计/人像写真/个人练习 | 比例、是否带字、风格收敛度全错 |
| 目标模型 | 是 | 从 17 个可选模型里选一个（清单见第 4 步表格）；不接受"不确定""你看着办"。**交付前必须落到具体模型**；`quick.py` 只给草稿默认值 | 语法、负向、参数全错 |
| 关键参数 | 看模型 | 比例、图内文字、透明底、变体 | 参数不合法，出图白跑 |

```bash
python3 scripts/intake.py --model flux --scene 电商主图        # 打印该问的问题
python3 scripts/intake.py --template --model moss -o brief.json # 空白清单
python3 scripts/intake.py --from-text "国潮茶叶海报，用FLUX，3:4"  # 从一句话预填
python3 scripts/intake.py --check brief.json                   # 体检，不足则退出码 1
```

**对话纪律**

- 一轮最多问 5 个问题，按上表顺序；其中**创意类最多 2 个**，问多了像审问。
- 能给默认值的直接给并标明（"按电商主图默认 1:1，要改告诉我"），不要反问"你想要什么比例"。
- 用户说"你看着办"：风格、比例可以代选并标 `[预测]`；**模型不能代选**，必须列清单等一句确认再往下走。
- 信息不足时**只输出澄清问题与建议**，不输出提示词。只有用户明说"先给个版本看看"，才带缺口出稿并标注缺口。

**风格没定，不要只反问"你想要什么风格"。** 给三个方向，让用户挑：

```bash
python3 scripts/intake.py --styles "安静 克制 旧"
```

输出是「稳妥（同调）/ 邻类（换族不换媒介）/ 反差（换媒介）」三档，每档附一句画面描述与命中词。三档的意义不同：稳妥保下限，邻类加一点新意，反差用来打破惯性也最容易翻车。用户还犹豫，就把画廊推给他（`assets/gallery.html`），看图比听描述快。

字面命中偏弱时脚本会自己提示——那种情况下不要硬推候选，直接建议看图或让用户说一个风格名。

**创意追问：挑 1–2 个，不要四个全问。** 主体平铺直叙（"一只茶壶"）时，从下面四个维度里选最相关的问：

| 维度 | 问法 | 为什么要问 |
|---|---|---|
| 情绪基调 | 想让人感觉到什么？一个词就够 | 决定光影与色彩走向 |
| 视角 | 用什么视角看它？ | 最便宜的创意来源 |
| 意外元素 | 加一笔打破常规的东西？ | 「有创意」与「好看但普通」的分界 |
| 一句话 | 如果这张图是一句话，你想说什么？ | 让主体与意外元素有共同指向 |

问到的答案要**并进主体句**，不要单独挂在提示词末尾——挂末尾会变成两条互不相干的指令。

判据：`scripts/intake.py --check` 退出码 0 才进第 1 步；非 0 时把 `missing` 列表转成问题问回去。

### 第 1 步 · 分清请求类型

| 类型 | 用户话术特征 | 走哪条路 |
|---|---|---|
| 直接要提示词 | "给我写个…的提示词" | 走第 2–5 步 |
| 只有感受没有风格 | "高级一点""日系干净""赛博感" | 先跑 `scripts/find_style.py`（它内置口语映射），给候选再组装 |
| 已指名风格 | "用宋式美学""侘寂风" | 校验名称 → 组装 |
| 要两个风格叠加 | "宋式 + 莫兰迪" | 组装前先跑冲突检查 |
| 只想挑/了解风格 | "有哪些国风风格""看看暗黑系" | `--category` 或关键词浏览，不组装 |
| 已有提示词要改 | "这段提示词换成水墨""哪里不对" | 先 `scripts/analyze_prompt.py` 反查，再改 |
| 一次要做一组图 | "做 5 张同风格配图" | `scripts/batch_prompt.py`，不要逐条手跑 |
| 指定了模型 | "用 SDXL / FLUX / MoS / Qwen / Krea 2 / Z-Image 出" | 锁定该模型，走第 0 步补齐参数，再按第 4 步渲染 |

判据：用户给了明确风格名，走"校验后组装"；只给感受，先用口语映射找 2–3 个候选并说明差异，让用户选或直接选最贴的一个（说明理由）。**用户指定了模型就锁定它**，不要换成自己更熟的模型——不同模型的效果差异是用户的选择，不是你的优化空间。

### 第 2 步 · 检索

```bash
python3 scripts/find_style.py 水墨 --top 5
python3 scripts/find_style.py "高级感 干净" --top 5
python3 scripts/find_style.py --category CN
python3 scripts/find_style.py --code CN-01
```

读结果时注意三件事：

1. 结果里的**「近邻易混」**不是装饰，是提醒你这些条目长得像，选错就出不来想要的画风。
2. 标了**「名称较宽/需补充限定」**的条目（风景、卡通、古典、抽象等 18 条），名字本身锁定不住画风，必须再叠一个具体风格，或在主体里写清材质与场景。
3. 标了**「在世艺术家/须转写特征」**的条目，不要把人名写进提示词。

命中为 0 时不要硬猜：换更具体的词，或先按分类浏览让用户看图选类。退出码 1 表示无匹配。

用户说不清要哪种时，直接给画廊入口 `assets/gallery.html` —— 173 张参考图按大类排好，点开有完整模板，比文字描述快得多。

### 第 3 步 · 组装

优先用脚本，不要手抄模板（手抄会漏段、会改词）：

```bash
python3 scripts/build_prompt.py --brief brief.json                        # 推荐：走清单
python3 scripts/build_prompt.py -s "主体描述" --style CN-01 --model flux --aspect 3:4
python3 scripts/build_prompt.py -s "主体描述" --style 新中式,莫兰迪色系 --model sdxl --aspect 3:4
python3 scripts/build_prompt.py -s "主体描述" --style DG-03 --model qwen-image --text-in-image "夜之城"
python3 scripts/build_prompt.py --brief brief.json --model moss --layout-json objects.json
```

`--model` 决定语法；`--platform` 是它的旧别名，两者等价。`--brief` 会先做完整性体检，不通过直接退出码 4，不生成提示词。

**组装前先看主体够不够。** 输出里的【主体体检】与【篇幅】两项合起来看：主体低于 60 字、或篇幅达成率低于 60%，就不要收工——先把主体按五要素补到 60–100 字（写法见 `references/subject-craft.md`），再组装。风格段那 50 字是常量，补不出细节；成稿短，几乎总是主体短。

脚本内部规则：第一个风格给全段；后续风格只覆盖 `--dims`（默认 color、light），并在输出里说明覆盖了哪段；同时跑三条冲突规则。

**排版与配色是另外两个维度**，不要塞进风格里：

```bash
python3 scripts/build_prompt.py -s "主体" --style CN-01 --model Qwen-Image-2.1 --layout IG-01 --color 月白
```

- `--layout` 决定「信息怎么摆」，画幅会自动取该图型的首选值；54 个号段见 `references/layouts.md`。
- `--color` 会**整段替换**风格原有的色彩段，其余五段不动；36 色见 `references/colors.md`。
- 不知道选哪个：`python3 scripts/layout_registry.py --suggest 小红书`。

`--strict` 会让高等级冲突直接失败（适合批量生产时防止带病交付）。

脚本同时输出 **【主体体检】**（0–100 分）。这是稳定性的关键：173 条风格段是常量，主体是唯一的变量，主体写崩了风格再准也救不回来。低于 85 分或出现 `[!]` 项，先按提示改主体再交付，改法见 `references/subject-craft.md`。

### 第 4 步 · 按目标模型适配

脚本已自动重排段落顺序、重写负向策略、换算合法分辨率。你要做的是**读懂它为什么这么改**，并补上脚本做不了的部分。

| 模型 | 语法要点 | 你还要做什么 |
|---|---|---|
| Z-Image-Turbo | 照片说明式；9 步、guidance 0 | 负向无效，需求改成正向描述 |
| Z-Image | 同语感但可写长；有 CFG | 别套 Turbo 的 9 步参数 |
| FLUX.2-klein-base-4B / 9B | 自然语句 50–150 词，主体前置；base 有 CFG（约 5） | **英译**；要写字用引号，不要文字就写 unmarked |
| FLUX.1-dev | 自然语句；guidance 3.5 在 FluxGuidance 节点 | **英译**；不加权重、不堆质量词 |
| FLUX.1-Kontext-dev | **编辑模型**：改什么 + 保留什么 | 提醒用户必须给输入图 |
| Krea-2-Turbo | 摄影词汇优先；8 步、CFG 1.0、mu 1.15 | **英译**；质量词是废字；材质词压过色词 |
| Krea-2 | 同语感，52 步 / CFG 3.5 | **英译**；出图慢，适合定稿 |
| Qwen-Image / -2512 / -2.1 | 中文结构化长句，文字渲染强 | 透明底要明写；正文 800 字内 |
| Qwen-Image-Edit / -2509 / -2511 | **编辑模型**：指令式，多图用「图1/图2」 | 提醒必须给输入图 |
| FireRed-Image-Edit-1.1 | **编辑模型**：指令式，中英文字都强 | 最多 3 张参考图；人脸保持别拉满 |
| MOSS-Image | 短句 + 可选 JSON 布局 | 排版走 BBox 模板；短优于长 |
| Fibo-2.0-dev | 短句即可（VGL 会展开成结构化描述） | 别手写超长 JSON；生成/编辑同一权重 |

四条判据：

1. **`language: en` 的模型必须英译**。脚本不替你翻（会瞎猜），只在 `translation_todo` 列出待译段。译完保留专名原形：Song Dynasty、Ukiyo-e、Dunhuang。
2. **负向策略看 `negative` 段的 `mode` 字段**：`separate` 走独立框、`inline` 并入句尾、`none`/`ignored` 直接不给。给 FLUX 塞负向词是无效劳动。
3. **参数只报档案里有的**。JSON 没写的采样值，一律说"以你的工作流为准"，不要编。
4. **长度上限看 `budget`**（`assets/models.json` 每条都有）：`prose` 按上下限看、`cn_structured` 只看上限、`json_layout`/`tag` 不以长度为准。别背数字，也别自己定 800 字——要查跑 `scripts/lint_prompt.py`，它读的就是这份档案。

**ComfyUI 接法不能省。** 用户全部在 ComfyUI 里跑，脚本会给出【ComfyUI 接法】块（工作流、尺寸约束、负向接哪）。两处最容易接错：

- FLUX 的引导强度在 `FluxGuidance` 节点，不是 KSampler 的 cfg；
- Qwen-Image 2.1 与 Z-Image Turbo 的开源权重不吃 `negative_prompt`，KSampler 的 negative 要接 `ConditioningZeroOut`，塞负向词等于白写。

**参考图可选。** 用户想要"就照这张图的画风"，加 `--with-ref`：

```bash
python3 scripts/build_prompt.py -s "主体" --style CN-12 --model flux2-klein-base-9b --with-ref
```

它会在提示词尾部追加隔离句（只提取线条、笔触、媒介、色彩、光影，不搬主体与构图），并在非 `--bare` 模式下给出图片路径。**隔离句不能省**——参考图里通常有具体主体，不隔离就会连碗带花一起搬进画面。

模型细节、选型决策表、新增模型的四步流程见 `references/models.md`；参考图数据集见 `references/dataset.md`。

### 第 5 步 · 处理冲突

脚本给出警告后，按等级处理：

- **high（媒介冲突/在世艺术家）**：不要直接交付。要么二选一，要么按 `fix` 里的方式在主体中显式分工，并把这话写进提示词。
- **medium（光影冲突/名称过宽）**：默认按建议改（用 `--dims` 排除 light），改完说明改了什么。
- **low（时代冲突/主体重复）**：可以保留，但要在交付时点明"这是有意混搭，融合逻辑是什么"。

### 第 6 步 · 批量（一次要一组图时）

一条一条手跑必然漂移。用批量脚本锁定风格与模型，它最后会给出**风格段哈希**作为一致性证据：

```bash
python3 scripts/batch_prompt.py --style CN-01 --model sdxl --aspect 3:4 --subjects list.txt
```

哈希唯一 = 所有条目风格段完全相同。若主体体检有不合格项，脚本退出码为 1 并列出待改编号。

### 第 7 步 · 工艺自检与交付

**先过闸门，再交付。** 组装完不等于是成品：长度是否超目标模型的预算、有没有混进权重语法、有没有把标签串当散文、五维有没有写漏、结尾有没有收束语、有没有写进人名、参照是不是超了「1 主 1 次」——这些都在 `scripts/lint_prompt.py` 里查，它按目标模型的 renderer 逐项分派，预算读 `assets/models.json`，人名读 `assets/living-names.json`，参照读 `references/style-anchors.md`。

```bash
python3 scripts/lint_prompt.py --model z-image-turbo --strict -f prompt.txt       # 交付前（严格口径）
python3 scripts/build_prompt.py -s "主体" --style CN-01 --model z-image-turbo --bare \
  | python3 scripts/lint_prompt.py --model z-image-turbo --strict --style CN-01 -  # 管道查
```

**交付一律带 `--strict`**（技能自己的交付流程按严格口径跑）。极简/抽象/编辑指令这类本来就不写色彩主张的稿子，加 `--no-aesthetic` 放行，并在交付说明里写明用了逃生门。`--style` 传本次选用的风格编号，可避免把「你自己选的那条风格」算成参照而误报。

`--model` 必填：预算与检查项都按它走，泛用场景写 `--model generic`，不要省略（省略等于放宽到通用档）。退出码 0 = 可以交付，1 = 有 FAIL，2 = 参数或输入错。

**什么时候必须跑**：① 每次交付前；② 批量生成前先跑一条验证语法与预算；③ 用户拿来一段现成提示词要你改时，先跑一遍定位问题。四类 renderer 的分派：`prose` 全查（含长度与标签密度）、`cn_structured` 不查标签密度、`json_layout` 跳过语法与长度、`tag` 只查人名与覆盖。不带 `--strict` 时只拦硬伤（超预算 / 禁用语法 / 标签堆砌 / 覆盖不足 / 人名 / 参照超限：库外锚点 >2、库内条目名 ≥4）；低于预算下限、缺色彩主张、缺动机光源只是提示。**交付口径是带 `--strict`**：这三类也判 FAIL（对应需求验收的五类缺陷）。抽象/极简/编辑指令用 `--no-aesthetic` 关掉审美层判读。

**只给提示词正文。** 不写解释、不列参数、不附接法说明——用户要的是能直接粘进 ComfyUI 的文字。

正文形态：**中文一段，空行，英文一段**。英文面向目标模型投喂，中文给自己核对与留档，两段段落顺序一一对应。

```bash
python3 scripts/build_prompt.py --brief brief.json --model <模型> --en-map en.json --bare
```

`--bare` 只打印正文。需要接法、参数、许可、体检时，去掉 `--bare`，或加 `--json`。这些是**过程信息**，默认不进交付。

**例外只有一种**：用户追问「这个模型怎么接」「能不能商用」，才补对应的一段说明，仍然不要塞回提示词里。

### 第 7 步补充 · 编辑模型

选了 Kontext / Qwen-Image-Edit 系 / FireRed 时，正文是**改图指令**，不是画面描述：

```
以图1为输入，把背景换成日落海滩，保持人脸与姿势不变。<风格段>
```

必须先确认「改什么」与「保留什么」（`--edit` / `--preserve`）。缺这两项，模型会自己乱改。

## 输出格式

默认（`--bare`）：

```
<中文提示词正文>

<英文提示词正文>
```

不加标题、不加编号、不加参数。两段之间空一行。

用户明确追问时才给补充块（仍与正文分开）：

```
【接法】KSampler 9 步 / CFG 1.0，负向接 ConditioningZeroOut
【许可】Apache-2.0，可商用
```

## 决策点

| 情况 | 做法 |
|---|---|
| 用户只给一句话、没提风格 | 不追问三轮。给 2–3 个候选（含编号与一句差异说明），推荐一个并说明理由，用户不反对就按推荐走 |
| 用户要的风格不在库里 | 说明库里最接近的 1–2 条，并指出缺什么；不要把现有条目硬套成他要的 |
| 用户要叠加 3 个以上风格 | 拒绝直接叠，改成"主风格 + 一个色彩/光影"，并说明为什么 |
| 主体本身已经写了风格名 | 提示重复加权，建议主体只写内容 |
| 主体体检低于 85 分 | 先改主体再交付，不要带着 `[!]` 项往下走 |
| 用户给了一段现成提示词 | 先反查再动刀：`scripts/analyze_prompt.py`，看它命中了哪些维度、缺哪些，只补缺的 |
| 模型未指定 | 问一句目标模型；用户说"不确定"就按场景推荐一款并说明理由。不要默认 SDXL 或 FLUX |
| 用户只说"随便来一张" | 主体与场景不能代猜，必须问；风格、比例、模型可以代选并标 `[预测]` |
| 指定的模型没有可靠参数 | 报"以你的工作流为准"，不要编步数与 CFG |
| 用户说"你帮我定风格" | 给三选一（稳妥/邻类/反差），每个附画面描述；不许只丢编号 |
| 主体太干、太常规 | 追问 1–2 个创意维度（情绪/视角/意外/一句话），把答案并进主体 |
| 用户要"5 个版本 / 多套方案" | 按 `references/walkthroughs.md` 案例 7 做一核五创：概念融合、叙事植入、尺度错位、材质替换、风格位移各出一套，且每套的差异点要一句话说清 |
| 用户说"做张小红书封面" | 先问清主题，用 `--suggest 小红书` 取 SM-01/02/09/12 里的一个，画幅用 3:4 |
| 用户要信息图 / 长图 | 确认文字量；密度高的（IG-04/06/10）必须选能写字的模型，否则出乱码 |
| 用户要"统一系列配色" | 用 `--color` 指定一个主色，全系列复用同一个 C 编号 |
| 要英文提示词 | `language: en` 的模型必须英译；按 `references/prompt-craft.md` 第四节处理，保留专名原形 |

## 资源

| 文件 | 什么时候读 |
|---|---|
| `assets/styles-173.json` | 需要原始模板、示例图名、六维段、`medium`/`flags` 时。**风格数据的唯一权威源** |
| `assets/models.json` | 需要某模型的语法、负向策略、参数、比例表、采集字段时。**模型数据的唯一权威源**；新增模型只改这里。每条的 `budget` 是**字数上限的唯一出处**，脚本与 `scripts/lint_prompt.py` 都读它 |
| `references/models.md` | 选型决策、逐模型语法与坑、新增模型的四步流程 |
| `references/layouts.md` | 54 个排版图型：家族、画幅、文字层级、场景映射 |
| `references/colors.md` | 36 个主题色与选色规则 |
| `assets/layouts.json` / `assets/colors.json` | 排版与配色的**唯一权威数据源** |
| `scripts/layout_registry.py` | 图型/配色的检索与场景推荐 |
| `references/dataset.md` | 参考图数据集的字段、重建方式、如何接进生成流程、能做与不能做的事 |
| `assets/gallery.html` | **图文画廊**：173 张参考图 + 模板，按大类排好，可筛选、搜索、放大、复制（双击即开，不依赖脚本） |
| `assets/dataset/manifest.jsonl` | 一行一条：编号、七维特征、模板、图片路径、哈希、原图出处 |
| `scripts/build_dataset.py` | 从分类目录重建缩略图与清单（新增风格后跑） |
| `references/taxonomy.md` | 需要浏览全部分类、确认标准名称与编号时。只做导航，不含模板正文 |
| `references/subject-craft.md` | 写主体、判断主体为什么不理想时。五要素公式、五类场景骨架、六条禁写 |
| `references/confusion.md` | 18 组易混风格逐维度对比（吉卜力 vs 动画导演条目、昭和风 vs 昭和复古…）；用户描述模糊时先读它 |
| `references/walkthroughs.md` | 7 个完整组装案例，含双语输出、氛围反查与「一核五创」的示范 |
| `references/prompt-craft.md` | 涉及叠加规则、冲突判定、负向词策略、跨语言改写、红线时 |
| `references/craft-color-light.md` | 要组织色彩比例、配色方案、色温关系，或把打光写实（光位/光比/光质/动机光源/材质交互）时。选色号去 `references/colors.md`，本篇管怎么用 |
| `references/craft-composition-lens.md` | 构图骨架、视觉重量、三层纵深、焦距/景深/机位怎么写时 |
| `references/pairing-rules.md` | 元素齐了但画面难看时：8 条搭配规则 + 常见雷区，人工自检用（脚本不查） |
| `references/creative-modules.md` | 主体太平、用户要"有点创意"或一次要给多套方案时：四类创意策略 + 组件库 |
| `references/style-anchors.md` | 需要库外参照时：24 条不覆盖的谱系，只写可观察特征，含姓名禁用规则 |
| `assets/living-names.json` | 姓名净化判据（23 人 + 可直接照抄的 `features`）；`scripts/name_guard.py` 负责加载与扫描，体检与 lint 共用 |
| `references/recipes.md` | 用户给的场景属于常见商业需求（茶器、国潮、人像、美食、绘本…）时，先看有没有现成配方 |
| `scripts/intake.py` | 第 0 步：打印问题、生成清单、体检充分度 |
| `scripts/quick.py` | 草稿通道：一句话出稿，自动认模型/比例/排版/色名，组装后就地自检；`--list-models` 看模型清单 |
| `scripts/find_style.py` | 任何检索动作 |
| `scripts/build_prompt.py` | 任何组装动作（`--model` 决定语法，`--brief` 走清单门禁） |
| `scripts/model_registry.py` / `scripts/model_render.py` | 档案的加载、校验与预算读取（`--list` / `--validate`）；四种渲染器的实现，只有新增语法体系时才要动 |
| `scripts/batch_prompt.py` | 一次生成多条同风格提示词 |
| `scripts/analyze_prompt.py` | 手上已有提示词，要反查它像哪条风格、缺什么 |
| `scripts/validate_library.py` | 数据被改动后自检（应输出 173 条 + 18 个模型、0 错误、100 分）；查档案、references 份数、姓名净化 |
| `scripts/lint_prompt.py` | 第 7 步闸门：成品提示词自检 8 项（长度/语法/密度/覆盖/收尾/人名/审美/参照），`--model` 必填、交付带 `--strict`；`--selftest` 可自测 |
| `scripts/rebuild_library.py` | 仅当原始 Markdown 更新后重建数据，需 `--source` 指定文件 |
| `scripts/make_gallery.py` | 数据更新后重新生成 gallery.html（依赖 dataset，先跑 build_dataset） |

## 红线

- **不把个人姓名当风格指令**：任何在世或生卒不明的创作者姓名都不写进提示词（库里 4 条已标记的条目也按此办：`JP-10`/`JP-11`/`JP-12`/`IL-19`），改写为可观察特征（判据与改写文本见 `assets/living-names.json`）；**交付前必须跑 `scripts/lint_prompt.py`**，`name` 项有 FAIL 就不许交。
- **索引可以写条目名，提示词不可以**：`references/taxonomy.md` 是分类目录，条目名是它的内容，故姓名扫描对它单点豁免（`validate_library.NAME_SCAN_SKIP_DOCS` 只有这一个文件）；提示词正文、模板与其他文档一律零容忍。
- **参照有数量上限（三档口径）**：库外锚点（`references/style-anchors.md` 的 24 条）**>2 判不合格**，正好 2 个只提示；库内条目名按 code 去重后 **=3 只提示、≥4 判不合格**（装配器本身允许 3 个风格，检查器不比它更严，但也不更松）。第 8 项就是这条，别在提示词里堆参照。
- **上限只认 `assets/models.json` 的 `budget`**：不背数字、不在提示词规则里另立上限；`syntax` 里不再有第二套 `max_words`，写文档时也不要复制一份预算表。
- 品牌与 IP 只描述风格特征，不复现受版权保护的具体角色。
- 宗教与民族题材不做戏谑化处理。
- 不编造"某模型实测最佳参数"这类无法复现的结论；平台参数标注整理时间。
- 不把"看起来像"当成"是"：检索结果里的候选差异必须基于模板文本，不凭印象描述风格。
- **信息不全不出稿**：主体、风格、场景、模型四项缺任一，只问不写。用户明说"先看看"才带缺口出稿，并标注缺了什么。
- **不臆断模型参数**：`assets/models.json` 没写的步数、CFG、采样器，一律回答"以你的工作流为准"。
- **不假装翻译**：英文优先模型的风格段，要么真的译好，要么明说"这段保留中文、需先译"，不要把中文段直接塞给 SDXL 还声称已适配。
- **不交半份**：只给中文或只给英文都算未完成。英文版不是中文版的附注，是投喂用的那一份。
- **不多话**：默认只交提示词正文。接法、参数、许可属于过程信息，用户追问才给，且不得编造。
- **高密度版面不配弱文字模型**：清单卡、参数表、数字阵列这类要写字的版式，Krea 2、Z-Image-Turbo 画不对字，必须提醒换 Qwen-Image / MOSS-Image / FLUX。
- **不把排版塞进风格**：排版是独立维度，写进风格描述会让模型两边都做一半。
- **不代选模型**：17 个模型的效果与许可差异很大，必须由用户确认；用户追问许可时如实说（Qwen-Image-2.1 需授权、FLUX.1-dev 非商用、Fibo 非商用）。

## 交付前自检

1. 五个槽位是否都确认过？特别是模型——是否由用户明确选中？
2. 主体体检 ≥85 分，无 `[!]` 项。
3. 篇幅达成率 ≥60%（成稿字数 ÷ 目标模型预算下限）？主体是否写到了 60–100 字？
3. 提示词里的每一段都能在 `assets/styles-173.json` 找到出处，或由主体自身提供。
4. 风格不超过 3 个，第二风格只覆盖 color/light。
5. 冲突警告已处理或已说明保留理由。
6. 模型语法与档案一致：负向策略、权重语法、分辨率都对得上。
7. `language: en` 的模型，风格段是否已按 `translation_todo` 译完？
8. 参数是否只报档案里有的？有没有替用户编步数？
9. 模型未被指定时，是否问过而不是默认某一款？
10. 中英两版都给了吗？段落顺序是否一一对应？
11. 若用户追问接法：节点是否与模型对得上（FLUX 的 guidance 节点、Qwen/Z-Image 的空条件、尺寸倍数）？许可与商用限制是否写清楚了？
12. 用了 `--layout` 时，画幅是否与图型匹配、信息密度是否超过模型写字能力？
13. 用了 `--color` 时，是否只保留了"一主一点缀"，没有堆三色以上？
14. 风格没定时，是否给了三个方向的候选（附画面描述），而不是只丢一个编号？
15. 是否追问了创意维度？追问的答案有没有并进主体，而不是挂在末尾？
16. `scripts/lint_prompt.py --model <目标模型>` 是否跑过、退出码为 0？有 WARN 时是否说明为什么可以放行？
17. 提示词里有没有出现在册姓名？有就按 `assets/living-names.json` 的 `features` 改写，不要自己编特征。
18. 参照数看了吗？库外锚点 >2 判不合格（≤1 放行、=2 只提示）；库内条目名 =3 只提示、≥4 判不合格；`scripts/lint_prompt.py` 的 `anchors` 项 FAIL 说明超了。

<!-- AUTHOR:BEGIN -->

## 关于作者

- **作者**：爱折腾的摄影大叔
- 公众号「爱折腾的摄影大叔」（lovephoto588）
- **许可**：MIT（代码） / CC BY 4.0（内容，需署名）
- **版权**：© 2026 爱折腾的摄影大叔，保留所有权利

> 转载、二次分发或商用，请保留上述署名与联系方式。

<!-- AUTHOR:END -->
