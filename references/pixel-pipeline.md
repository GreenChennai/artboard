# artboard 位图配方引擎(pixel;PS 对照的调整/滤镜/图层)

> **本册是"像素级加工"的唯一真相源**。三层分工:
> `imaging.md` = 工序快查(裁/缩/压/转,点哪条命令)| `image-language.md` = 为什么这么处理
> (角色/处理链)| **本册** = 怎么调、配方怎么写、怎么批量。
> 调用关系:`pixel.py`(像素加工)→ `imageops.py`(编码/规格收口)→ 进项目。

---

## 1. 快速上手(五步)

```bash
S="<skill>/scripts"
python $S/pixel.py deps                                   # ① 看能力矩阵
python $S/pixel.py levels --in a.jpg -o b.png \
    --params '{"black":0.04,"gamma":1.05,"white":0.96}'    # ② 单 op 试调(透传 JSON 参数)
python $S/pixel.py levels --in a.jpg -o b.png --params '{}' --mask luminosity  # ③ 局部应用
python $S/pixel.py recipe validate my.json                # ④ 配方校验(乱序/缺依赖在此拦)
python $S/pixel.py recipe batch my.json --in-dir imgs/ --out-dir out/        # ⑤ 批量套用
```

## 2. 能力矩阵(P0 全落地;依赖分级)

| 域 | ops | 依赖 |
|---|---|---|
| **调整 18 项(P0-A)** | levels / curves / brightness-contrast / exposure / vibrance / hsl / color-balance / black-white / channel-mixer / photo-filter / gradient-map / selective-color / shadows-highlights / posterize / threshold / invert / desaturate / match-color | 纯 Pillow+numpy,**全支持 `--mask`** |
| **滤镜 12 项(P0-B)** | blur-gaussian / blur-motion / blur-radial / sharpen-usm / sharpen-highpass / noise-reduce / add-noise / emboss / find-edges / glow / vignette / oil-paint | blur-motion、blur-radial、noise-reduce 有 cv2 更强;**oil-paint 需要 opencv-contrib(无近似,缺就报错)** |
| **图层(P0-C)** | blend(**25 种混合模式**)/ layer-stack / fill / stroke / drop-shadow | 纯 Pillow+numpy;sRGB 域**近似实现,非色卡级一致** |
| 选择/通道(P1) | select-color-range / magic-wand / refine-edge / channel-split/merge / alpha-extract | **未实现**(本轮 P0 范围外;需要时走 cutout.py / 手工链) |
| 变换(P1) | warp-perspective / free-transform | **未实现**(几何收口仍走 `imageops`) |

`python $S/pixel.py deps` = 能力矩阵(本机实测);**缺依赖的 op 默认报错 + 安装提示,不静默**;
`--allow-degrade` 才允许降级,且结果 JSON `degraded[]` 非空(诚实降级姿态)。

## 3. 配方格式(recipe.json;版本 1)

```json
{ "version": 1,
  "stages": [
    { "op": "auto-orient" },
    { "op": "levels", "channel": "rgb", "black": 0.04, "gamma": 1.05, "white": 0.96 },
    { "op": "curves", "points": [[0,0],[0.25,0.20],[0.75,0.80],[1,1]] },
    { "op": "hsl", "range": "all", "sat": -0.08, "light": 0.03 },
    { "op": "gradient-map", "stops": [["#12291c",0.0],["#eef3ec",1.0]], "mask": "luminosity" },
    { "op": "sharpen-usm", "amount": 0.6, "radius": 1.2, "threshold": 3 },
    { "op": "vignette", "amount": 0.25 } ],
  "output": { "format": "png" } }
```

- `stages` 顺序 = `image-language.md §七` 固定处理链(方向→几何→抠图→色调→合成→输出),
  **乱序 `recipe validate` 直接报错**;
- `mask`(所有调整/滤镜可用,= PS「调整层+蒙版」):`luminosity` / `luminosity-inv` /
  `alpha` / `color:#rrggbb,tol` / `shape:rect:l,t,r,b` / `shape:circle:cx,cy,r` /
  `shape:gradient:top` / 灰度图路径;
- CLI 单 op 用 `--params '<json>'` 传参数、`--mask` 传蒙版;
- 配方放 `assets/recipes/`(公共)或项目 `src/img/recipes/`(私有)。

## 4. 公共配方库(`assets/recipes/`,首批 6 套,全过 validate)

| 配方 | 一句话 | 适用 |
|---|---|---|
| `film-warm.json` | 胶片感(轻降对比+暖高光青阴+颗粒+暗角) | vlog/生活方式 |
| `grey-editorial.json` | 高级灰(降饱和+中间调压灰) | 编辑排版/科技 |
| `night-cold.json` | 冷调夜景(压高光+偏蓝+发光) | 城市/夜景/游戏 |
| `food-warm.json` | 暖食(自然饱和+暖滤镜+柔高光) | 食品/烘焙 |
| `mono-editorial.json` | 单色编辑(黑白红权重+沉暗部) | 人物/海报 |
| `promo-punch.json` | 高对比促销(拉对比+提饱和) | 促销大字报背景 |

> 用法:`pixel.py recipe run assets/recipes/food-warm.json --in <图> -o <出>`。
> 效果叠加纪律不变:一图特效 ≤3 种、上版前 `imageops probe` 体检。

## 5. 参数区间表(经验起点,不是标准)

| op | 常用区间 | 说明 |
|---|---|---|
| levels | black 0–0.08 / gamma 0.8–1.3 / white 0.92–1 | 别拉满,黑场 >0.06 多半脏 |
| curves | 2–4 个控制点,x 严格递增 | 单调;别做"蛇形" |
| vibrance | ±0.4;sat ±0.3 | 自然饱和优先于 hsl 全局 |
| photo-filter | density 0.1–0.25,preserve_luminosity=true | 保留明度才不脏 |
| shadows-highlights | 各 ≤0.35 | 超过就开始假 |
| sharpen-usm | amount 0.4–0.8 / radius 1–2 / threshold 3–6 | 半径大=假边 |
| add-noise | 0.01–0.03 monochrome | 彩噪只在造景用 |
| vignette | ≤0.35,feather 0.5–0.8 | 暗角是引导不是压黑 |

## 6. 与既有链路的衔接

1. **抠图后调色**(materials.md §3):`cutout.py`(透明件)→ 透明件**不做全图 tone**
   (image-language §七)→ 需要色调的透明主体用 `pixel.py <op> --mask alpha` 做局部;
2. **输出收口**仍走 `imageops`(compress/convert/平台规格)——pixel 只做像素加工;
3. 交付前:`imageops probe` 体检 + 压字跑 `contrast-check`(4.5:1 / 3:1);
4. 配方存进 `src/img/recipes/` = 改稿可重放(调色改了只重放配方,不重拍)。

## 7. 不做项(提示即拒)

- **AI 生成式填充 / content-aware fill / 生成式扩展**:本技能不调 AI 生图;
- **人像液化 / 变形瘦脸**:越界(人物真实性红线);
- **超分 / 插帧模型**:属 MomentShift,不进本引擎;
- **WebGL 图像编辑**:渲染导出语境不存在交互。

## 8. 自检(6 条)

1. 配方序符合 image-language §七 吗?(validate 报乱序)
2. 局部调整优于全图——所有该带 `--mask` 的都带了吗?
3. `pixel deps` 能力齐吗?缺依赖是**报错**而不是静默跳过吗?
4. 输出收口走 `imageops` 了吗?(体积/格式)
5. 成品跑过 `probe` + 压字跑过 `contrast-check` 吗?
6. 配方存进 `src/img/recipes/` 了吗?(可重放)

## 本册用到的脚本

| 脚本 | 何时用 | 一行示例 |
|---|---|---|
| `pixel.py` | 调整/滤镜/图层配方引擎 | `python scripts/pixel.py levels --in a.jpg -o b.png --params '{}'` |
| `imageops.py` | 输出收口(compress/convert) | `python scripts/imageops.py compress <图> --target 500KB` |

> 参数的权威说明在脚本自身 `--help`(不在此复制);全量索引见 `docs/scripts.md`。
