# 模型手册（17 个开源模型）

> 数据源是 `../assets/models.json`，本文件是它的人读版。冲突以 JSON 为准。
> 参数核对日期 **2026-11-04**；模型迭代快，投喂前对照官方模型卡。

## 一、总表

| # | 模型 | 任务 | 语法 | 步数 | CFG / guidance | 负向 | 许可 |
|---|---|---|---|---|---|---|---|
| 1 | Z-Image-Turbo | 文生图 | 自然语句 | 9 | 0.0 | weak | 以官方模型卡为准 |
| 2 | Z-Image | 文生图 | 自然语句 | 30 | 4.0 | separate | 以官方模型卡为准 |
| 3 | FLUX.2-klein-base-4B | 文生图 | 自然语句 | 20 | 5.0 | separate | Apache-2.0 |
| 4 | FLUX.2-klein-base-9B | 文生图 | 自然语句 | 24 | 5.0 | separate | Apache-2.0 |
| 5 | FLUX.1-dev | 文生图 | 自然语句 | 28 | 3.5 | ignored | FLUX.1 [dev] Non-Commercial License |
| 6 | FLUX.1-Kontext-dev | 编辑 | 中文结构化 | 28 | 2.5 | ignored | FLUX.1 [dev] Non-Commercial License |
| 7 | Krea-2-Turbo | 文生图 | 自然语句 | 8 | 1.0 | none | Krea 2 Community License |
| 8 | Krea-2 | 文生图 | 自然语句 | 52 | 3.5 | separate | Krea 2 Community License |
| 9 | Qwen-Image | 文生图 | 中文结构化 | 20 | 2.5 | none | Qwen License（以模型卡为准） |
| 10 | Qwen-Image-2512 | 文生图 | 中文结构化 | 20 | 2.5 | none | Qwen License（以模型卡为准） |
| 11 | Qwen-Image-2.1 | 文生图 | 中文结构化 | 30 | 4.0 | none | Qwen Research License（商用需授权） |
| 12 | Qwen-Image-Edit | 编辑 | 中文结构化 | 20 | 2.5 | none | Qwen License（以模型卡为准） |
| 13 | Qwen-Image-Edit-2509 | 编辑 | 中文结构化 | 20 | 2.5 | none | Qwen License（以模型卡为准） |
| 14 | Qwen-Image-Edit-2511 | 编辑 | 中文结构化 | 20 | 2.5 | none | Qwen License（以模型卡为准） |
| 15 | FireRed-Image-Edit-1.1 | 编辑 | 中文结构化 | 30 | 4.0 | separate | Apache-2.0 |
| 16 | MOSS-Image | 文生图 | JSON 布局 | 50 | 3.0 | separate | Apache-2.0 |
| 17 | Fibo-2.0-dev | 两者皆可 | 自然语句 | 30 | 5.0 | separate | CC BY-NC 4.0（仅非商用，商用需与 Bria 签约） |

看负向一列：`none`/`ignored` 表示塞了也没用；`separate` 才有独立负向框；`weak` 只在有 CFG 时才勉强起作用。

## 二、逐个要点

### 1. Z-Image-Turbo

- 渲染器 `prose`；语言 `both`；任务 文生图
- 像写照片说明：主体 + 状态 + 环境 + 质感 + 镜头
- 中文友好，语序自然即可
- 需要干净画面就正向加「无文字」
- ComfyUI：Z-Image 官方 Turbo 模板：Load Diffusion Model + CLIPLoader → CLIPTextEncode → KSampler
- 尺寸：64 的倍数，1024×1024 起
- 负向接法：Turbo 不吃负向，接 ConditioningZeroOut

### 2. Z-Image

- 渲染器 `prose`；语言 `both`；任务 文生图
- 与 Turbo 同一套语感，但可以写得更长更细
- 有 CFG，负向可以用了
- 同样中文友好
- ComfyUI：Z-Image 官方 Base 模板，参数按模型卡
- 尺寸：64 的倍数
- 负向接法：常规负向输入可用

### 3. FLUX.2-klein-base-4B

- 渲染器 `prose`；语言 `en`；任务 文生图
- 文字编码器是 Qwen3-4B，不是 CLIP/T5 那套老习惯
- 提示词写成完整句子，50–150 词最佳，主体前置
- 图内文字能力强：要写字就用引号给原文，不需要文字时把 surface 描述成 unmarked / clean
- ComfyUI：ComfyUI 内置 FLUX.2 klein 4B 模板：Load Diffusion Model + CLIPLoader → CLIPTextEncode → KSampler
- 尺寸：64 的倍数：1024×1024 / 1152×896 / 896×1152 / 1536×1024
- 负向接法：base 接负向可用；蒸馏版接空条件

### 4. FLUX.2-klein-base-9B

- 渲染器 `prose`；语言 `en`；任务 文生图
- 文字编码器是 Qwen3-8B，不是 CLIP/T5 那套老习惯
- 提示词写成完整句子，50–150 词最佳，主体前置
- 图内文字能力强：要写字就用引号给原文，不需要文字时把 surface 描述成 unmarked / clean
- ComfyUI：ComfyUI 内置 FLUX.2 klein 9B 模板：Load Diffusion Model + CLIPLoader → CLIPTextEncode → KSampler
- 尺寸：64 的倍数：1024×1024 / 1152×896 / 896×1152 / 1536×1024
- 负向接法：base 接负向可用；蒸馏版接空条件

### 5. FLUX.1-dev

- 渲染器 `prose`；语言 `en`；任务 文生图
- 自然语言，不加权重、不堆质量词
- T5 编码器吃长句，主体先出现
- 图内文字用引号
- ComfyUI：UNETLoader + DualCLIPLoader(clip_l/t5xxl) → CLIPTextEncode → FluxGuidance → KSampler
- 尺寸：64 的倍数，1024×1024 / 832×1216
- 负向接法：接 ConditioningZeroOut

### 6. FLUX.1-Kontext-dev

- 渲染器 `cn_structured`；语言 `en`；任务 编辑
- 这是**编辑模型**：提示词是「改什么 + 保留什么」的指令，不是画面描述
- 一句话说清动作，别写风格堆词
- 要换文字就直接给原文
- ComfyUI：ComfyUI 内置 Kontext 模板：Load Image → VAE Encode → ReferenceLatent → KSampler
- 尺寸：跟随输入图，或 64 的倍数
- 负向接法：接空条件

### 7. Krea-2-Turbo

- 渲染器 `prose`；语言 `en`；任务 文生图
- 自然语言 + 摄影词汇：焦段、时段、胶片、光向
- 质量词（masterpiece/8k）在这里是废字
- 材质与具体色名比抽象形容有用
- 要写字就用引号
- ComfyUI：ComfyUI Krea-2 模板：Load Diffusion Model + CLIPLoader(qwen3vl_4b) → KSampler
- 尺寸：1K–2K，16 的倍数（2048×2048 / 1536×2048）
- 负向接法：接 ConditioningZeroOut

### 8. Krea-2

- 渲染器 `prose`；语言 `en`；任务 文生图
- 与 Turbo 同一套语感，但更吃细节与变化
- 调参空间比 Turbo 大
- 训练 LoRA 用这一版
- ComfyUI：ComfyUI Krea-2 RAW 模板
- 尺寸：1K 左右，16 的倍数
- 负向接法：常规负向可用

### 9. Qwen-Image

- 渲染器 `cn_structured`；语言 `both`；任务 文生图
- 中文结构化长句最稳：主体 → 场景 → 风格 → 镜头 → 氛围 → 细节
- 文字渲染是强项，标题/段落给原文与层级
- 尺寸为 16 的倍数
- ComfyUI：ComfyUI Qwen-Image 模板：CLIPLoader(qwen) → CLIPTextEncode → KSampler
- 尺寸：16 的倍数，1328×1328 / 1664×928
- 负向接法：接 ConditioningZeroOut

### 10. Qwen-Image-2512

- 渲染器 `cn_structured`；语言 `both`；任务 文生图
- 与 Qwen-Image 同源，中文长句 + 强文字渲染
- 细节与排版比初版稳，仍建议给明确层级
- 尺寸 16 的倍数
- ComfyUI：ComfyUI Qwen-Image-2512 模板（与 Qwen-Image 同构）
- 尺寸：16 的倍数
- 负向接法：接空条件

### 11. Qwen-Image-2.1

- 渲染器 `cn_structured`；语言 `both`；任务 文生图
- 7B 统一模型，原生 RGBA 透明背景
- 文字排版强，长标题给原文与层级
- 最多 10 张参考图（编辑场景）
- 版本号不等于发布顺序：3.0 早于 2.1
- ComfyUI：ComfyUI 官方 Qwen-Image 2.1 生成/编辑模板
- 尺寸：16 的倍数，1328×1328 / 1664×928
- 负向接法：接 ConditioningZeroOut

### 12. Qwen-Image-Edit

- 渲染器 `cn_structured`；语言 `both`；任务 编辑
- 这是**编辑模型**：提示词 = 改什么 + 保留什么，不是从零描述画面
- 初代编辑模型，指令式改图。
- 引用多张输入图时用「图1/图2」指代
- 换文字要给原文与字体风格
- ComfyUI：ComfyUI Qwen-Image-Edit 模板：Load Image → VAE Encode → Text Encode → KSampler
- 尺寸：跟随输入图或 16 的倍数
- 负向接法：接空条件

### 13. Qwen-Image-Edit-2509

- 渲染器 `cn_structured`；语言 `both`；任务 编辑
- 这是**编辑模型**：提示词 = 改什么 + 保留什么，不是从零描述画面
- 2509 支持多图输入（最多 3 张），适合换装/合成/参考编辑。
- 引用多张输入图时用「图1/图2」指代
- 换文字要给原文与字体风格
- ComfyUI：ComfyUI Qwen-Image-Edit 模板：Load Image → VAE Encode → Text Encode → KSampler
- 尺寸：跟随输入图或 16 的倍数
- 负向接法：接空条件

### 14. Qwen-Image-Edit-2511

- 渲染器 `cn_structured`；语言 `both`；任务 编辑
- 这是**编辑模型**：提示词 = 改什么 + 保留什么，不是从零描述画面
- 2511 为 2509 的后续更新，一致性与文字编辑更稳。
- 引用多张输入图时用「图1/图2」指代
- 换文字要给原文与字体风格
- ComfyUI：ComfyUI Qwen-Image-Edit 模板：Load Image → VAE Encode → Text Encode → KSampler
- 尺寸：跟随输入图或 16 的倍数
- 负向接法：接空条件

### 15. FireRed-Image-Edit-1.1

- 渲染器 `cn_structured`；语言 `both`；任务 编辑
- 小红书 FireRed 团队的**编辑模型**，指令式改图
- 中英双语文字渲染都强，「把 X 改成 Y」直接说
- 最多 3 张参考图，用「图1/图2」指代
- 改文字、风格迁移、老照片修复是强项
- ComfyUI：ComfyUI FireRed-Image-Edit 模板：Load Image(1–3) → Text Encode → KSampler
- 尺寸：跟随输入图，或 16 的倍数
- 负向接法：可用，精准 4–6 项

### 16. MOSS-Image

- 渲染器 `json_layout`；语言 `both`；任务 文生图
- 原生中英双语，短句优于长句（内置 enhancer）
- JSON 布局可精确控制元素位置与图内文字
- 做 2D 动漫与排版用 SFT 权重
- ComfyUI：ComfyUI 0.42+ 内置四套模板：Base/SFT × 有/无 BBox
- 尺寸：16 的倍数，512–1024
- 负向接法：模板自带负向输入

### 17. Fibo-2.0-dev

- 渲染器 `prose`；语言 `both`；任务 两者皆可
- Bria 的统一模型：文生图 + 编辑同一套权重
- 背后是 VGL 结构化描述：短句会被展开成结构化 caption，所以写短、写具体
- 拆开写光/构图/材质/相机，比堆形容词稳
- 生成与编辑都能用，最多 4 张参考图
- ComfyUI：ComfyUI 走 Fibo 2.0 模板或 Diffusers 分支（需 bria-vgl 工具链）
- 尺寸：16 的倍数，约 1MP：1024×1024 / 1424×800 / 1248×832
- 负向接法：可用

## 三、ComfyUI 速查

| 模型 | 工作流 | 尺寸 | 负向接哪 |
|---|---|---|---|
| Z-Image-Turbo | Z-Image 官方 Turbo 模板：Load Diffusion Model + CLIPLoader → CLIPTextEncode → KSampler | 64 的倍数，1024×1024 起 | Turbo 不吃负向，接 ConditioningZeroOut |
| Z-Image | Z-Image 官方 Base 模板，参数按模型卡 | 64 的倍数 | 常规负向输入可用 |
| FLUX.2-klein-base-4B | ComfyUI 内置 FLUX.2 klein 4B 模板：Load Diffusion Model + CLIPLoader → CLIPTextEncode → KSampler | 64 的倍数：1024×1024 / 1152×896 / 896×1152 / 1536×1024 | base 接负向可用；蒸馏版接空条件 |
| FLUX.2-klein-base-9B | ComfyUI 内置 FLUX.2 klein 9B 模板：Load Diffusion Model + CLIPLoader → CLIPTextEncode → KSampler | 64 的倍数：1024×1024 / 1152×896 / 896×1152 / 1536×1024 | base 接负向可用；蒸馏版接空条件 |
| FLUX.1-dev | UNETLoader + DualCLIPLoader(clip_l/t5xxl) → CLIPTextEncode → FluxGuidance → KSampler | 64 的倍数，1024×1024 / 832×1216 | 接 ConditioningZeroOut |
| FLUX.1-Kontext-dev | ComfyUI 内置 Kontext 模板：Load Image → VAE Encode → ReferenceLatent → KSampler | 跟随输入图，或 64 的倍数 | 接空条件 |
| Krea-2-Turbo | ComfyUI Krea-2 模板：Load Diffusion Model + CLIPLoader(qwen3vl_4b) → KSampler | 1K–2K，16 的倍数（2048×2048 / 1536×2048） | 接 ConditioningZeroOut |
| Krea-2 | ComfyUI Krea-2 RAW 模板 | 1K 左右，16 的倍数 | 常规负向可用 |
| Qwen-Image | ComfyUI Qwen-Image 模板：CLIPLoader(qwen) → CLIPTextEncode → KSampler | 16 的倍数，1328×1328 / 1664×928 | 接 ConditioningZeroOut |
| Qwen-Image-2512 | ComfyUI Qwen-Image-2512 模板（与 Qwen-Image 同构） | 16 的倍数 | 接空条件 |
| Qwen-Image-2.1 | ComfyUI 官方 Qwen-Image 2.1 生成/编辑模板 | 16 的倍数，1328×1328 / 1664×928 | 接 ConditioningZeroOut |
| Qwen-Image-Edit | ComfyUI Qwen-Image-Edit 模板：Load Image → VAE Encode → Text Encode → KSampler | 跟随输入图或 16 的倍数 | 接空条件 |
| Qwen-Image-Edit-2509 | ComfyUI Qwen-Image-Edit 模板：Load Image → VAE Encode → Text Encode → KSampler | 跟随输入图或 16 的倍数 | 接空条件 |
| Qwen-Image-Edit-2511 | ComfyUI Qwen-Image-Edit 模板：Load Image → VAE Encode → Text Encode → KSampler | 跟随输入图或 16 的倍数 | 接空条件 |
| FireRed-Image-Edit-1.1 | ComfyUI FireRed-Image-Edit 模板：Load Image(1–3) → Text Encode → KSampler | 跟随输入图，或 16 的倍数 | 可用，精准 4–6 项 |
| MOSS-Image | ComfyUI 0.42+ 内置四套模板：Base/SFT × 有/无 BBox | 16 的倍数，512–1024 | 模板自带负向输入 |
| Fibo-2.0-dev | ComfyUI 走 Fibo 2.0 模板或 Diffusers 分支（需 bria-vgl 工具链） | 16 的倍数，约 1MP：1024×1024 / 1424×800 / 1248×832 | 可用 |

**三个高频踩坑**

1. **FLUX 系**的引导强度在 `FluxGuidance` 节点，不是 KSampler 的 `cfg`；把 3.5 填进 cfg 会过约束。
2. **Qwen-Image 系、Z-Image-Turbo、Krea-2-Turbo 不吃负向**：KSampler 的 negative 必须接空条件，塞负向词等于白写。
3. **尺寸倍数**：FLUX/FLUX.2/Z-Image 取 64 的倍数；Qwen/MOSS/Fibo 取 16 的倍数。差一位就可能糊或报错。

## 四、渲染器对照

| renderer | 语法 | 模型 |
|---|---|---|
| `prose` | 自然语句，不加权重 | Z-Image-Turbo、Z-Image、FLUX.2-klein-base-4B、FLUX.2-klein-base-9B、FLUX.1-dev、Krea-2-Turbo、Krea-2、Fibo-2.0-dev |
| `cn_structured` | 中文结构化长句 / 编辑指令 | FLUX.1-Kontext-dev、Qwen-Image、Qwen-Image-2512、Qwen-Image-2.1、Qwen-Image-Edit、Qwen-Image-Edit-2509、Qwen-Image-Edit-2511、FireRed-Image-Edit-1.1 |
| `json_layout` | 短句 + 可选 JSON 布局 | MOSS-Image |

## 五、新增模型：四步

1. 在 `../assets/models.json` 的 `models[]` 加一项，必填字段见 `model_registry.REQUIRED`。
2. 先想办法复用现有四种 renderer；只改 `segment_order` 就能表达「这个模型更看重光还是材质」。
3. 确实需要新语法，才在 `../scripts/model_render.py` 加分支，并同步 `RENDERERS` 与 JSON 的 `renderers` 数组。
4. 跑 `python3 scripts/validate_library.py`，必须 0 错误 100 分；再跑一条真实组装。

**不要**：只改文档不改 JSON、在脚本里硬编码模型名单、把未核实的采样参数当默认值。

## 六、参数时效

每个模型带 `verified`（当前 2026-11-04）与 `sources`。超过 6 个月复核三项：默认步数/CFG、原生分辨率、负向是否仍有效。
