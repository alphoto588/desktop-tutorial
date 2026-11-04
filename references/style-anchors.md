# 库外风格参照（只描述可观察特征）

> **本表只描述可观察特征，不指向具体创作者。** 表内每一条都是"看得见的东西"（光怎么打、色怎么配、构图怎么切），不是"某个人的风格"——照表写特征即可，不要往里加姓名（判据见 `../assets/living-names.json`）。

**为什么需要参照**：写"复古"模型只能猜；写"单一侧窗光从左侧压进来，其余沉进暗部"，模型立刻知道要什么光、什么色、什么质感。参照是最高效的风格控制手段。

**与 173 库的关系**：这里只收库里**没有**的参照。库里已覆盖的画派直接查库，不要重复写：印象派（WE-01）、巴洛克（WE-10）、文艺复兴（WE-21）、新古典（WE-12）、浪漫主义（WE-13）、拉斐尔前派（WE-16）、象征主义（WE-15）、表现主义（WE-03）、超现实主义（WE-05）、波普（WE-22）、抽象表现（WE-04）、文人画（CN-29）、青绿山水（CN-16）、敦煌壁画（CN-18）、工笔（CN-14）、水墨（CN-12）、禅画（CN-33）、浮世绘（JP-01）、琳派（JP-02）、狩野派（JP-03）、宋式美学（CN-01）。

**用法铁律**：参照是锚，不是复制。一句提示词里最多两个参照（1 主 1 次），且**必须写出你要的那个具体特征**（光？色？构图？质感？）。只丢参照名，等于没写。

## 一、绘画与时期（4 条）

| 参照 | 可观察特征 | 可借用的东西 | 英文锚点 | 库内相近 |
|---|---|---|---|---|
| 荷兰黄金时代的室内窗光 | 单一侧窗作唯一光源，暗背景托住亮部，日常器物与静物同权 | 一束窗光压主体、其余沉暗；材质靠反光说话 | Dutch Golden Age window light, single source from the left | EX-18（人像版本） |
| 德国新客观主义 | 冷峻锐利的直视写实，平光、无修饰、日常场景的社会观察视角 | 克制的纪实冷感，用来压住过度唯美 | New Objectivity, cool detached realism, unadorned daylight | 无 |
| 南宋山水的「一角半边」 | 主体偏居一角，大面积留白，湿墨淡染，近景实、远景虚 | 空灵与不对称；用留白承载情绪 | Southern Song one-corner composition, wet ink wash | CN-01（气质近，结构不同） |
| 金石碑拓 | 黑白拓片、纸纹与石花、字口残损、边缘漫漶 | 古拙肌理与文字感，适合做器物与书法的底 | stone rubbing, epigraphy texture, cracked and mottled ink | 无 |

## 二、摄影手法（10 条，只写手法不写人）

| 参照 | 可观察特征 | 可借用的东西 | 英文锚点 |
|---|---|---|---|
| 分区曝光的黑白风光 | 从极黑到极白的完整灰阶，前后景一致清晰，无彩色干扰 | 极致的影调控制，适合山岳、建筑、极简 | zone-system black-and-white landscape, full tonal range |
| 几何切割的街头瞬间 | 主体与背景构成互为呼应，人物未被干预，35mm 自然透视 | 抓拍的必然感；构图靠等，不靠摆 | decisive-moment street geometry, unposed candid |
| 隔湿玻璃的碎片色块 | 朦胧遮挡的前景切掉半个画面，饱和色斑被玻璃分割 | 朦胧、碎片化色彩，情绪含蓄 | color seen through rain-streaked glass, fragmented color blocks |
| 平淡日常的高饱和色 | 正面机位、平光，色彩浓度高于题材重要性 | 让普通物件变得可看的办法 | mundane subject in saturated color, frontal flat light |
| 电影化舞台布光 | 场景像搭出来的布景，光源可见，日常里的异样静止 | 场景叙事、超现实日常；人物常背对或停滞 | staged cinematic tableau, visible practical rig |
| 浓烈色彩直视人像 | 被摄者直视镜头，环境色参与构图，饱和度高 | 人像强度；环境不是背景而是论据 | saturated direct-gaze portrait, environmental color |
| 单点硬主光的叙事肖像 | 硬主光压在人物一侧，背景留一件可读的道具，皮肤保留毛孔与细纹 | 名人肖像式的故事感，不磨皮 | single hard key light on one side, readable narrative prop behind, visible skin texture |
| 集锦仿水墨摄影 | 多底合成，远山层层退淡，宣纸般的灰调与颗粒 | 中国画式的摄影空间，适合山水与园林 | pictorialist ink-photography composite, layered fading ranges |
| 逆光街巷的可见光束 | 逆光光束斜切画面，人物成剪影，尘埃与蒸汽被照亮 | 市井的空间层次；光束就是构图 | backlit street with visible light shafts, dust in the air |
| 长曝光的海平线 | 浪被抹平，画面只有一条水平分割，天空极简 | 极简与时间感，适合做留白底 | long-exposure seascape, a single horizon line, smoothed water |

## 三、影像与影片质感（10 条）

影片名可以留，创作者姓名不留。

| 参照 | 可观察特征 | 可借用的东西 | 英文锚点 |
|---|---|---|---|
| 橙雾与青蓝的科幻夜景 | 暖橙与冷青对撞，巨型投影或雕像压住画面，尘埃作介质 | 色温对撞 + 巨物尺度 | amber-and-teal haze, colossal holographic figure |
| 克制实景光与烟尘光束 | 光源都在画面内（灯、窗、火），雾中透出光束，整体冷调留一处暖 | 真实感强的电影光，不炫技 | practical-light realism, beams through smoke |
| 霓虹绿与暗红对撞的窄巷 | 微倾构图，湿地面反射招牌光，抽格拖影 | 情绪化的城市夜景 | neon-green and deep-red collision, tilted framing, wet reflections |
| 单色块面主导 | 单一色相铺满九成画面，人物作小面积对比色点，色块边界干净无渐变 | 大色块叙事，海报感强 | monochromatic color blocking, a small contrasting figure |
| 自然光长镜头 | 自然光、静态机位、门框作出深浅景，构图不加干预 | 静观与克制，纪实底色 | natural-light long take, static framing through doorways |
| 天气驱动的群像构图 | 雨、风、旗、尘同时参与画面，群像沿对角线排布，前景剪影压边 | 用天气造动态，不要动作也能有张力 | weather-driven composition, banners and rain, foreground silhouettes |
| 绝对对称的粉彩 | 正面机位、严格对称、粉彩平涂、截面式剖面 | 秩序感与平面化色卡 | symmetrical pastel tableau, front-on framing |
| 极简巨物的单色调 | 单一冷调铺满，尘土与雾把远景吞掉，微小人影作尺度参照 | 史诗感靠参照物，不靠形容词 | brutalist monochrome scale, dust haze, tiny figures |
| 橙青对撞的废土色卡 | 高饱和橙与青并存，沙尘与破布作介质，硬斜阳 | 废土、动作片的高对比配色 | orange-and-teal wasteland, sand haze |
| 粉彩色阶随年代推移 | 同一场景的配色随年代变化，平面化对称构图，装饰细节繁密 | 用色彩讲时间，系列图很好用 | pastel color scripting by era |

## 四、从参照到可执行描述（三步）

1. **选参照**：1 主 1 次，第二次参照只能管一个维度（通常是光或构图）。
2. **点出一个特征**：光、色、构图、质感，四选一，写具体。
3. **和题材接上**：把特征嫁接到你的主体上，而不是另起一段。

对照：

- 只丢名字（无效）：`荷兰黄金时代风格`
- 写出特征（有效）：`室内只有左侧一扇窗透光，光落在陶罐的釉面上，其余沉进深棕的暗部`

**跨域混搭公式**（制造独特性，但要防大杂烩）：

> `[参照A的光] × [参照B的构图] × [你的题材]`

例：`只用荷兰黄金时代那种单侧窗光，配南宋山水的「一角半边」构图，主体是一只现代玻璃杯`。

## 五、禁忌

| 禁忌 | 说明 |
|---|---|
| 参照堆叠 | 一句里出现三个以上参照，模型会平均化，哪个都不像 |
| 只写名字 | 不点具体特征，等于没写 |
| 时代错配 | 古典光配赛博题材可以，但要显式说明融合逻辑（见 `prompt-craft.md` 时代冲突） |
| 文化符号混用 | 中式题材配西式光位可以，中日韩符号不可互换 |
| 与画质锚点打架 | 写了水墨质感就别再写 8K 照片级锐利 |
| 写入姓名 | 任何个人姓名都不作为风格指令；命中 `../assets/living-names.json` 即判不合格 |
