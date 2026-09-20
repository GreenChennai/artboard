# artboard 失效案例库(failures)

> 承接 `ITERATION.md` §4 Step 2 的纪律:只记**真实发生过**的失效,不记"可能会";每条带复现,可检索、可归因。
> 修复状态三档:**已修(注明版本)/ 已探明未修(走 ITERATION 环)/ 绕行中**。
> 入库动作:实际使用中每次跑出意外,2 分钟内追加一行;这是 ITERATION 环 Gate 0 触发来源①(真实失败)的唯一入口。
> 修复时按 `ITERATION.md` 六门禁走:Gate 1 先定真相源 → Gate 2 实跑验证 → 本表回填"已修 + 版本"。

## 失效台账

| 日期 | 症状 | 复现 | 根因 | 修复 | 状态 |
|---|---|---|---|---|---|
| 2026-09-21 | `imageops.py card --shadow` 直接 `TypeError: unsupported operand type(s) for +: 'int' and 'str'` | 对任意图跑 `python scripts/imageops.py card <图> --shadow 0,18,40,#00000059`(2026-09-21 波2 位图链实跑;2026-09-21 复核代码仍在) | `_img_compose.py` `_shadow_layer()` 对 `dx,dy,blur,color` 做 `split(",")` 后 `blur` 仍是字符串,`W + blur * 4` 变成 `int + str`(后面的 `int()/float()` 强转在崩溃点之后,永远执行不到) | 未修 | **已探明未修**,走 ITERATION 环 |
| 2026-09-21 | `imageops.py thumb` 报 `AttributeError`(读取不存在的 `args.format`) | 跑 `python scripts/imageops.py thumb <图>`(波2 实跑;复核仍在) | `imageops.py` thumb 子命令把 `--format` 注册成 `dest="format_out"`,而 `_img_geom.py` `cmd_thumb()` 读的是 `args.format`——dest 与消费端字段名不一致 | 未修 | **已探明未修**,走 ITERATION 环 |
| 2026-09-21 | `imageops.py contrast-check` 输出 JSON 失败(`Object of type bool_ is not JSON serializable`) | 对压字图跑 `python scripts/imageops.py contrast-check <图> --box … --fg …`(波2 实跑;复核仍在) | `_img_probe.py` `cmd_contrast_check()` 的 `ratio/worst` 来自 numpy 数组运算(numpy float64),`pass_normal/pass_large` 是 numpy bool_;`_img_core.emit()` 的 `json.dumps` 不认 numpy 标量 | 未修 | **已探明未修**,走 ITERATION 环 |
| 2026-09-21 | `imageops.py --in` 收绝对路径 glob 直接 `NotImplementedError: non-relative patterns are unsupported`(全族子命令受累;montage 已自守) | `python scripts/imageops.py probe --in "E:/某目录/*.png"`(波4 montage 实现期探明;复核仍在) | `_img_core.py` `input_expand()` 把 `--in` 的值直接喂 `pathlib.Path.glob()`,而 `Path.glob` 不接受绝对模式 | 未修 | **已探明未修**,走 ITERATION 环 |
| 2026-09-21 | `imageops.py watermark` 单点九锚文字水印必崩 `KeyError`(tile 模式正常) | `python scripts/imageops.py watermark <图> --text "©x" --position br --opacity 0.35`(波4 联络表角标实跑) | `_img_compose.py` 文字水印单点分支:九锚坐标字典以锚点名为键,查询却用了另一套键(键位错位) | 未修 | **已探明未修**,走 ITERATION 环 |
| 2026-09-21 | `imageops.py tone/card` 用 `--out` 指定单文件输出时报 `AttributeError: 'str' object has no attribute 'write_bytes'` | `python scripts/imageops.py tone <图> --saturation 0 -o out.png`(渲染验收轮实跑;`--out-dir` 正常) | `_img_compose.py` 输出路径处理把 `--out` 字符串直接当 `Path` 用(未包 `Path()`);缺省命名路径正常 | 未修 | **已探明未修**,走 ITERATION 环 |

> 以上六条均出自 2026-09-21 执行轮实跑(波2 位图链 / 波4 montage / 渲染验收;证据与当轮绕行方式见迭代台账)。
> 按 ITERATION 纪律"每轮只做 P0 + 能验证的 P1",本轮是设计知识分册迭代(不动脚本的硬约束),
> 六条留给下一轮**代码迭代环**(Gate 0 ①真实失败 → Gate 2 实跑验证),修复时逐条单独 commit。

## 记录纪律(防台账烂掉)

1. **只记真实发生**:有复现命令才入表;"我猜可能会"的进 backlog,不进本表;
2. **当天记,带锚点**:症状写用户可感知的现象,复现写到命令级,根因写到 `文件:函数`;
3. **修了必须回填**:状态改"已修",注明版本号;连续两轮没人修的"已探明未修"项,下轮排期时默认升为 P1;
4. **一条一因**:同一症状多因时拆行,否则修复验证无法归因(ITERATION 反模式"一次修一串")。
