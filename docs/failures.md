# artboard 失效案例库(failures)

> 承接 `ITERATION.md` §4 Step 2 的纪律:只记**真实发生过**的失效,不记"可能会";每条带复现,可检索、可归因。
> 修复状态三档:**已修(注明版本)/ 已探明未修(走 ITERATION 环)/ 绕行中**。
> 入库动作:实际使用中每次跑出意外,2 分钟内追加一行;这是 ITERATION 环 Gate 0 触发来源①(真实失败)的唯一入口。
> 修复时按 `ITERATION.md` 六门禁走:Gate 1 先定真相源 → Gate 2 实跑验证 → 本表回填"已修 + 版本"。

## 失效台账

| 日期 | 症状 | 复现 | 根因 | 修复 | 状态 |
|---|---|---|---|---|---|
| 2026-09-21 | `imageops.py card --shadow` 直接 `TypeError: unsupported operand type(s) for +: 'int' and 'str'` | 对任意图跑 `python scripts/imageops.py card <图> --shadow 0,18,40,#00000059`(2026-09-21 波2 位图链实跑;2026-09-21 复核代码仍在) | `_img_compose.py` `_shadow_layer()` 对 `dx,dy,blur,color` 做 `split(",")` 后 `blur` 仍是字符串,`W + blur * 4` 变成 `int + str`(后面的 `int()/float()` 强转在崩溃点之后,永远执行不到) | `_shadow_layer()` 解析即转数值 + 参数个数/数值校验(`BAD_SHADOW`);顺带修好阴影位移:此前 `dx/dy` 被丢弃、`pad` 不留偏移量,阴影方向被裁 | **已修**(v1.13.0) |
| 2026-09-21 | `imageops.py thumb` 报 `AttributeError`(读取不存在的 `args.format`) | 跑 `python scripts/imageops.py thumb <图>`(波2 实跑;复核仍在) | `imageops.py` thumb 子命令把 `--format` 注册成 `dest="format_out"`,而 `_img_geom.py` `cmd_thumb()` 读的是 `args.format`——dest 与消费端字段名不一致 | `cmd_thumb()` 改读 `format_out`(与其它子命令口径统一),并补上此前被忽略的 `--out` | **已修**(v1.13.0) |
| 2026-09-21 | `imageops.py contrast-check` 输出 JSON 失败(`Object of type bool_ is not JSON serializable`) | 对压字图跑 `python scripts/imageops.py contrast-check <图> --box … --fg …`(波2 实跑;复核仍在) | `_img_probe.py` `cmd_contrast_check()` 的 `ratio/worst` 来自 numpy 数组运算(numpy float64),`pass_normal/pass_large` 是 numpy bool_;`_img_core.emit()` 的 `json.dumps` 不认 numpy 标量 | `_wcag_ratio()` 入口 `float()` 化、返回 `float(...)`;两个判定改 `bool(...)` | **已修**(v1.13.0) |
| 2026-09-21 | `imageops.py --in` 收绝对路径 glob 直接 `NotImplementedError: non-relative patterns are unsupported`(全族子命令受累;montage 已自守) | `python scripts/imageops.py probe --in "E:/某目录/*.png"`(波4 montage 实现期探明;复核仍在) | `_img_core.py` `input_expand()` 把 `--in` 的值直接喂 `pathlib.Path.glob()`,而 `Path.glob` 不接受绝对模式 | 新增 `_glob()`:绝对模式拆「盘根 + 相对模式」再拼;montage 的特例守卫随之删除 | **已修**(v1.13.0) |
| 2026-09-21 | `imageops.py watermark` 单点九锚文字水印必崩 `KeyError`(tile 模式正常) | `python scripts/imageops.py watermark <图> --text "©x" --position br --opacity 0.35`(波4 联络表角标实跑) | `_img_compose.py` 文字水印单点分支:九锚坐标字典以锚点名为键,查询却用了另一套键(键位错位) | 坐标表补回「位置名 → anchor 码」查询,再由码取坐标;九锚 + tile 十种位置实测全通 | **已修**(v1.13.0) |
| 2026-09-21 | `imageops.py tone/card` 用 `--out` 指定单文件输出时报 `AttributeError: 'str' object has no attribute 'write_bytes'` | `python scripts/imageops.py tone <图> --saturation 0 -o out.png`(渲染验收轮实跑;`--out-dir` 正常) | `_img_compose.py` 输出路径处理把 `--out` 字符串直接当 `Path` 用(未包 `Path()`);缺省命名路径正常 | `card` / `watermark` / `tone` 三处统一 `pathlib.Path(args.out)` | **已修**(v1.13.0) |
| 2026-09-22 | `exif-fix <目录>` 全部条目报 `TypeError: object of type 'int' has no len()` | `python scripts/imageops.py exif-fix <目录> --out-dir out` | `imageops.py` `_cmd_exif_fix()` 把 `out.stat().st_size`(int)塞给 `result_item()` 的第 4 位(形参是**编码后字节**,内部 `len()`) | 改传 `out.read_bytes()` | **已修**(v1.13.0) |
| 2026-09-22 | 位置参数给**目录**时直接 `PermissionError`(整族子命令) | `python scripts/imageops.py exif-fix .` | `_img_core.input_expand()` 把位置参数原样当文件交给 PIL,目录没被展开 | 位置参数是目录时递归展开图片(默认扩展名白名单,可 `--ext` 收窄);空目录给 `INPUT_NOT_FOUND` | **已修**(v1.13.0) |

> 前六条出自 2026-09-21 执行轮的实跑(波2 位图链 / 波4 montage / 渲染验收),本轮(2026-09-22)代码迭代环一次收口。
> 后两条为本轮修复期间新暴露的相邻缺陷,按「一条一因」入表。

## 记录纪律(防台账烂掉)

1. **只记真实发生**:有复现命令才入表;"我猜可能会"的进 backlog,不进本表;
2. **当天记,带锚点**:症状写用户可感知的现象,复现写到命令级,根因写到 `文件:函数`;
3. **修了必须回填**:状态改"已修",注明版本号;连续两轮没人修的"已探明未修"项,下轮排期时默认升为 P1;
4. **一条一因**:同一症状多因时拆行,否则修复验证无法归因(ITERATION 反模式"一次修一串")。

## 复查记录(06-J:每轮至少一次;"已探明未修"连续两轮未修自动升 P1)

| 日期 | 范围 | 结论 |
|---|---|---|
| 2026-09-26 | 全表 8 条(2026-09-21/22 波次) | **8 条全部"已修(v1.13.0)"**,无"已探明未修"与"绕行中"在案 → 本轮无升级项;上游 Kiln 两条另见 `docs/upstream-issues.md`(不属本表,属上游台账) |
