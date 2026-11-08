# 一杯饮料，一座小店 · WorkBuddy 技能

上传一张咖啡／奶茶／饮料照片，自动生成一张**由杯子组成的 2D 等轴测微缩门店插画**，并附一张「真实原图 + 插画」高清对比图。

风格参考：粗黑描边、纯色平涂、45° 等轴测、品牌英文标题、楼梯遮阳棚、吉祥物与绿植，像 Adobe Illustrator 做的商业 IP 插画海报，而不是 3D 渲染。

---

## 一、它会给你什么

| 文件 | 内容 |
|---|---|
| `<原名>_illustration.png` | 一张**独立完整**的等轴测门店插画（不是从对比图裁出来的） |
| `<原名>_compare.png` | 真实原图 + 插画的无裁切拼接图（竖版左右拼 / 横版上下拼） |

默认输出到当前工作区 `out/cup-shop-illustration/`。

---

## 二、安装

技能目录整体放到用户级技能目录即可，无需 pip install、无需 API Key：

```
C:\Users\<你的用户名>\.workbuddy\skills\cup-shop-illustration\
```

Windows（Git Bash）一键安装（把 `<源码目录>` 换成实际路径）：

```bash
mkdir -p "$HOME/.workbuddy/skills/cup-shop-illustration"
cp -r "<源码目录>/cup-shop-illustration/." "$HOME/.workbuddy/skills/cup-shop-illustration/"
```

安装后新开一轮对话即可触发（技能列表会自动扫描到 `SKILL.md`）。

### 依赖

| 依赖 | 说明 |
|---|---|
| WorkBuddy 内置 `ImageGen` | 负责图生图，**每张约消耗 5–10 积分**，调用前助手会先告知 |
| Python 3 + Pillow | 预处理与拼接。WorkBuddy 托管 venv `~/.workbuddy/binaries/python/envs/default/Scripts/python.exe` 已内置 Pillow；用系统 Python 时 `pip install Pillow` 即可 |
| 无网络请求、无密钥 | `scripts/imgtool.py` 纯本地运行，不上传任何图片 |

---

## 三、使用

直接把照片拖进对话，说一句：

> 用「杯子门店插画」技能，把这张照片变成等轴测微缩门店插画

或更自然地说「把这张咖啡照片变成由杯子组成的小店」「奶茶杯子做成等轴测插画」都会触发。

**选填信息**（不填就从照片自动识别，识别不出不会瞎编）：

| 项 | 例子 |
|---|---|
| 品牌名称 | Grid Coffee / 茶百道 |
| 饮品名称 | Americano / 黑糖珍珠奶茶 |
| 联名信息 | 某 IP 联名款 |
| 其他特色 | 云南秋珀庄园豆、加燕麦奶、少冰 |

技能会**一次跑完**，不逐步找你确认：预处理 → 识别 → 组装提示词 → 出图 → 自检 → 拼接 → 交付两张 PNG，并附上完整提示词原文。

---

## 四、可调项

| 想改 | 怎么做 |
|---|---|
| 背景色 | 直接说「换成奶油黄背景」 |
| 标题 | 说「只要主标题，去掉副标题」 |
| 加产地/联名元素 | 说「加咖啡果枝和庄园 A 字牌」 |
| 多出几版挑一张 | 说「出 2 版，拼个对比图」（每版各消耗一次积分） |
| 拼接间距/底色 | 改 `compose --gap 24 --pad 24 --bg "#FFFFFF"` |
| 保真度 | 助手调 `input_fidelity`：跑了杯型→调高，像临摹→调低 |

---

## 五、手工调用脚本（可选）

```bash
PY="$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
SK="$HOME/.workbuddy/skills/cup-shop-illustration/scripts/imgtool.py"

# 1. 预处理 + 打印信息卡（方向、亮度、主色）
"$PY" "$SK" prepare "D:/photo/latte.jpg"

# 2. 无痕去掉右下角平台水印（推荐，不裁地台、不伤绿叶）
"$PY" "$SK" cleanwm "out/illustration.png" --out "out/illustration_clean.png"

# 3. 拼接（--photo 一定传用户上传的原始照片）
"$PY" "$SK" compose --photo "D:/photo/latte.jpg" --art "out/illustration_clean.png" --out "out/compare.png"

# 4. 备用：底部裁切去水印（可能切到地台，少用）
"$PY" "$SK" trim "out/illustration.png" --bottom 0.06 --mode pad --out "out/illustration_trim.png"

# 5. 多版插画拼宫格（可选）
"$PY" "$SK" sheet out/v1.png out/v2.png --out out/sheet.png --cols 2

# 查看全部参数
"$PY" "$SK" --help
```

`compose` 的行为：以插画原始像素为基准（插画不缩放），把真实原图等比缩放对齐；白色间隔 24px、外边距 24px；比例差异用留白吸收，**不裁切、不拉伸、不改内容**。

---

## 六、常见问题

| 问题 | 处理 |
|---|---|
| 生成的像 3D 渲染 / 写实照片 | 提示词第 3 段风格锚点前置并追加负面词表，最多重出一次 |
| 杯型或品牌色被换掉 | 把 `input_fidelity` 调到 `high`，并在识别段写死主色与 logo 位置 |
| 中文招牌乱码 | 默认全英文标题；中文小字牌用 Pillow 后期叠加，别整张重出 |
| HEIC / 特殊格式读不了 | 先由系统转成 PNG/JPG 再跑，脚本会明确报错，不会静默失败 |
| 右下角有「AI生成 WORKBUDDY」水印 | 平台强制叠加，`footnote: ""` 去不掉；用 `cleanwm`（默认 `selective` + `--threshold 160`，只抹白字、不伤绿叶地台），别用 `trim` 裁地台。右下角有浅色装饰时把 threshold 调高到 190–210 |
| 想省积分 | 一次只出一张；重出最多一次；本地脚本不消耗积分 |

---

## 七、目录结构

```
cup-shop-illustration/
├── SKILL.md                     # 技能主流程（六步、硬规则、可调项）
├── README.md                    # 本文件
├── references/
│   ├── prompt-master.md         # 完整可复用提示词模板 + 槽位 + 三套示例 + 负面词
│   └── diagnose.md              # 照片识别卡、九条自检、失败修法表
└── scripts/
    └── imgtool.py               # prepare / cleanwm / compose / trim / sheet 五个本地子命令
```

**隐私说明**：照片只作为本地文件传给 WorkBuddy 内置图像生成工具，技能脚本本身不联网、不写密钥、不上传文件；对外分享本技能目录时无需脱敏（不含任何凭据）。
