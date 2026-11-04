# 风格参考图数据集

把 173 张散落在分类目录里的参考图，整理成**技能自包含、可校验、可被脚本与画廊直接消费**的数据集。

原图 51 MB 且位于技能目录之外（`../../..` 的十个分类文件夹），一旦打包分发或换机就会断链。所以这里做的是**缩略图进包、原图路径留档**：体积压到 4 MB，来源仍可回溯到具体文件。

## 一、目录结构

```
assets/dataset/
├── images/
│   ├── 001-100/001.webp … 100.webp
│   └── 101-200/101.webp … 173.webp      # 按 100 张分桶，与编号一一对应
├── _grid/
│   ├── CN.webp  JP.webp  WR.webp …      # 每大类一张拼版，快速扫
└── manifest.jsonl                        # 一行一条，机器可读
assets/reference-map.json                 # 编号 → 图片 + 哈希，生成流程用
```

缩略图：最长边 480 px、WebP q72、`method=6`。173 张共约 4.0 MB，10 张拼版另计。

## 二、manifest 字段

| 字段 | 说明 |
|---|---|
| `id` / `code` | 原文档编号（1–173）与分类码（CN-01） |
| `name` / `name_en` | 中文名、英文名 |
| `category` / `category_name` | 大类码与中文名 |
| `medium` | 媒介（photo / painting / print / illustration / animation / digital / 3d …） |
| `traits` | **七维特征**：色彩 / 构图 / 材质 / 光影 / 画质 / 风格 / 情绪，逐段原文 |
| `template` | 完整提示词模板，`【画面主体】` 为唯一槽位 |
| `image` | 缩略图相对路径 |
| `source` | 原图相对路径（含分类目录），用于回溯与重新生成 |
| `sha1` / `bytes` / `width` / `height` | 完整性校验与体积 |

`../assets/reference-map.json` 是它的瘦身版：只留 `code / name / image / sha1 / source`，供生成时快速取图。

## 三、三条使用路径

**1. 浏览**：打开 `../assets/gallery.html`。卡片带参考图，可按大类筛选、按关键词搜、点开看大图与完整模板，← → 翻页。选中某类时上方会显示该类拼版图。

**2. 生成时带参考图**：给组装命令加 `--with-ref`。

```bash
python3 scripts/build_prompt.py -s "主体描述" --style CN-12 --model flux2-klein-base-9b --with-ref --bare
```

它会做两件事：

- 在提示词末尾追加隔离子句——「参考图仅用于提取画风（线条、笔触、媒介、色彩与光影），不要沿用图中的主体、构图、场景与文字」；
- 非 `--bare` 模式下打印该风格的缩略图路径与原始出处，供你在 ComfyUI 里接到 IPAdapter / Reference Latent 这类节点。

**为什么必须带这句**：参考图里往往有具体主体。不隔离，模型会把参考图的碗、花、人一起搬进画面，风格对了但内容错了。

**3. 导出做 LoRA 或微调**：`../assets/dataset/manifest.jsonl` 一行一条，可直接转 CSV/JSON 喂给训练脚本；`source` 字段指向原图，需要高分辨率时按它取，不必用缩略图凑。

## 四、新增一个风格：四步

1. 把图片放进对应分类目录，命名 `编号. 风格名.jpg`（编号接在 173 之后）。
2. 在源 Markdown 里加条目，跑 `python3 scripts/rebuild_library.py --source <md>` 重建 `../assets/styles-173.json`。
3. 跑 `python3 scripts/build_dataset.py` —— 只处理新增或原图更新的条目，已有缩略图不重复转码。
4. 跑 `python3 scripts/make_gallery.py` 与 `python3 scripts/validate_library.py`，应为 0 错误。

想换缩略图规格：`--max 640 --quality 80`。想改分桶大小：改 `../scripts/build_dataset.py` 的 `BUCKET`，同时清理旧目录。

## 五、为什么这样组织

- **编号当文件名**：`../assets/dataset/images/001-100/001.webp` 比「宋式美学.webp」稳，改名不改路径，脚本按数字定位。
- **分桶存放**：一个目录塞 173 个文件，文件管理器与图床都难受；按 100 一桶，增删不影响其他桶。
- **缩略图与索引分离**：图片只负责看，`../assets/dataset/manifest.jsonl` 负责查。重建图片不会破坏索引。
- **保留 source**：缩略图是派生物，原图路径留下，随时能回溯或重新生成高分辨率。
- **拼版图**：每类一张 `_grid`，扫一眼就能判断这一类的整体气质，比逐张点开快。

这套结构不是某个现成项目的规定，而是「编号 + 分桶 + 索引 + 派生图」在处理几百张图时的常见做法。

## 六、预期效果

**能确定的**

- 画廊从"只有文字"变成"图文对照"，选风格时不用再去文件夹里翻图，173 张 4 MB，本地秒开。
- 参考图有稳定路径与哈希，同一编号在任何机器上指向同一张图；换图会改 sha1，可发现。
- 带 `--with-ref` 生成的提示词，明显降低"风格对了但主体被参考图带跑"的概率——这是隔离句的直接作用。

**不能保证的**

- 缩略图不是训练级分辨率。做 LoRA 请按 `source` 取原图。
- 参考图只能约束"画风倾向"，不能替代 LoRA。要稳定复现某个画风，仍建议在该风格图上训一个小 LoRA，本数据集正好提供成组的正样本。
- 173 张里每类只有 3–37 张，`SB` 类仅 3 张，做分类训练会严重不均衡；它们更适合做**检索与提示词锚点**，不适合直接当分类训练集。

## 七、维护

图片是派生产物，随时可重建：删掉 `assets/dataset/` 再跑 `../scripts/build_dataset.py` 即可，源图不受影响。`../assets/gallery.html` 同理。唯一需要人工维护的是源 Markdown 与分类目录里的图片本身。
