"""PDF 文字断层修复:把 Chromium 逐字 Td/Tj 定位合并成单条 TJ 数组。

Chromium 打印的 PDF 里一个 BT 块形如:
    BT /F17 24 Tf 1 0 0 -1 24 33 Tm <53EA> Tj 26.88 0 Td <2140> Tj ... ET
Illustrator 把块内每个 Td+Tj 拆成独立文字对象(逐字断层,不可编辑)。
本模块把每个 BT 块重写为单条 TJ:`[<53EA> -120 <2140> ...] TJ`,字距差值
用 TJ 数值逐字精确保真(需要内嵌字体的 /W 度量表),AI 即还原为整句可编辑。

仅重写安全形态(Tf/Tm/Td/Tj/TJ/Tc/Tw);含 Tz/TL/引号等未知形态的块原样跳过。
视觉零变化:逐字位置由 TJ 数值精确复现。
"""

from __future__ import annotations

import pikepdf


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _font_entry(font_obj) -> dict:
    """字体 → {widths: cid→1/1000em 宽, two_byte, dw}。"""
    entry = {"widths": {}, "two_byte": False, "dw": 1000.0}
    try:
        if font_obj.get("/Subtype") == pikepdf.Name("/Type0"):
            entry["two_byte"] = True
            desc = font_obj.DescendantFonts[0]
            entry["dw"] = float(desc.get("/DW", 1000))
            if "/W" in desc:
                arr = list(desc.W)
                i = 0
                while i < len(arr):
                    c = int(arr[i])
                    if i + 1 < len(arr) and not isinstance(arr[i + 1], (int, float)):
                        for k, w in enumerate(arr[i + 1]):
                            entry["widths"][c + k] = float(w)
                        i += 2
                    else:
                        c2, w = int(arr[i + 1]), float(arr[i + 2])
                        for cc in range(c, min(c2 + 1, c + 4096)):
                            entry["widths"][cc] = w
                        i += 3
        else:
            first = int(font_obj.get("/FirstChar", 0))
            for k, w in enumerate(font_obj.get("/Widths", [])):
                entry["widths"][first + k] = float(w)
    except (KeyError, TypeError, ValueError):
        pass
    return entry


def _cids(raw: bytes, two_byte: bool) -> list[int]:
    if not two_byte:
        return list(raw)
    out = [((raw[i] << 8) | raw[i + 1]) for i in range(0, len(raw) - 1, 2)]
    if len(raw) % 2:
        out.append(raw[-1])
    return out


def _merge_bt_block(block: list, fonts: dict) -> list | None:
    """合并一个 BT..ET 指令区间(不含 BT/ET 本身);不安全返回 None。"""
    font = size = None
    tm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    line = (0.0, 0.0)
    tc = 0.0
    shows: list[dict] = []
    ok = True

    for ins in block:
        op = str(ins.operator)
        if op == "Tf":
            newfont = str(ins.operands[0])
            if shows and (newfont != font):
                ok = False
            font, size = newfont, _num(ins.operands[1])
        elif op == "Tm":
            m = [_num(v) for v in ins.operands[:6]]
            if shows and any(abs(v) > 1e-6 for v in
                             (m[0] - 1, m[1], m[2], m[3] + 1)):  # 非翻转平移阵
                ok = False
            tm = m
            new_line = (m[4], m[5])
            if shows and abs(new_line[1] - line[1]) > 0.5:
                ok = False  # 块内换行:不合并
            line = new_line
        elif op == "Td":
            a, b = _num(ins.operands[0]), _num(ins.operands[1])
            line = (line[0] + tm[0] * a + tm[2] * b, line[1] + tm[1] * a + tm[3] * b)
        elif op == "TD":
            a, b = _num(ins.operands[0]), _num(ins.operands[1])
            line = (line[0] + tm[0] * a + tm[2] * b, line[1] + tm[1] * a + tm[3] * b)
        elif op == "Tc":
            tc = _num(ins.operands[0])
        elif op in ("Tz", "TL", "Ts", "'", '"', "T*"):
            ok = False
        elif op in ("Tj", "TJ"):
            if font is None or font not in fonts:
                ok = False
                break
            fd = fonts[font]
            if op == "Tj":
                raw = bytes(ins.operands[-1])
            else:
                raw = b"".join(bytes(x) for x in ins.operands[0]
                               if isinstance(x, (pikepdf.String, str, bytes)))
            shows.append({"font": font, "size": size, "raw": raw, "tm": tm,
                          "x": line[0], "y": line[1], "tc": tc,
                          "cids": _cids(raw, fd["two_byte"])})
            if shows and len(shows) > 4000:
                ok = False  # 异常巨块:不合并
                break

    if not ok or not shows:
        return None

    # 同字体+字号+基线 为一段
    segments: dict[tuple, list[dict]] = {}
    order: list[tuple] = []
    for s in shows:
        key = (s["font"], round(s["size"], 3), round(s["y"], 2))
        if key not in segments:
            segments[key] = []
            order.append(key)
        segments[key].append(s)

    def op(name: str, operands=None):
        return pikepdf.ContentStreamInstruction(
            operands if operands is not None else [], pikepdf.Operator(name))

    new_ops: list = []
    for key in order:
        seg = sorted(segments[key], key=lambda s: s["x"])
        fd = fonts[key[0]]
        fsize = key[1]
        nat = lambda cid: fd["widths"].get(cid, fd["dw"]) / 1000.0 * fsize
        tarr: list = []
        prev_end = None
        for s in seg:
            if prev_end is not None:
                gap = s["x"] - prev_end
                if abs(gap) > 0.01:
                    tarr.append(-round(gap / fsize * 1000))
            tarr.append(pikepdf.String(s["raw"]))
            adv = sum(nat(c) for c in s["cids"]) + s["tc"] * len(s["cids"])
            prev_end = s["x"] + adv
        new_ops.append(op("BT"))
        new_ops.append(op("Tf", [pikepdf.Name(key[0]), key[1]]))
        m = seg[0]["tm"]
        new_ops.append(op("Tm", [m[0], m[1], m[2], m[3], m[4], m[5]]))
        new_ops.append(op("TJ", [pikepdf.Array(tarr)]))
        new_ops.append(op("ET"))
    return new_ops


def merge_text_runs(pdf_path: str) -> dict:
    """就地把 PDF(页内 + 嵌套 Form XObject)所有文字块合并为单条 TJ。"""
    stats = {"blocks": 0, "merged": 0}

    def _streams(res) -> list:
        out = []
        if res is None or "/XObject" not in res:
            return out
        for _, xo in res.XObject.items():
            if xo.get("/Subtype") == pikepdf.Name("/Form"):
                out.append(xo)
                if "/Resources" in xo:
                    out += _streams(xo.Resources)
        return out

    with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        for page in pdf.pages:
            targets = [page] + _streams(page.get("/Resources"))
            for obj in targets:
                res = obj.get("/Resources")
                fonts: dict[str, dict] = {}
                if res is not None and "/Font" in res:
                    for fname, fobj in res.Font.items():
                        fonts[str(fname)] = _font_entry(fobj)
                try:
                    ops = pikepdf.parse_content_stream(obj)
                except Exception:
                    continue
                new_ops: list = []
                block: list = []
                in_bt = False
                changed = False
                for ins in ops:
                    opn = str(ins.operator)
                    if opn == "BT":
                        in_bt, block = True, []
                        continue
                    if opn == "ET" and in_bt:
                        in_bt = False
                        stats["blocks"] += 1
                        merged = _merge_bt_block(block, fonts) if fonts else None
                        if merged is not None:
                            new_ops += merged
                            changed = True
                            stats["merged"] += 1
                        else:
                            new_ops.append(pikepdf.Operator("BT"))
                            new_ops += block
                            new_ops.append(pikepdf.Operator("ET"))
                        continue
                    (block if in_bt else new_ops).append(ins)
                if in_bt and block:
                    new_ops.append(pikepdf.Operator("BT"))
                    new_ops += block
                if changed:
                    data = pikepdf.unparse_content_stream(new_ops)
                    if isinstance(obj, pikepdf.Stream):  # Form XObject 流
                        obj.write(data)
                    else:                                # 页面:Contents 可能是数组/字典,整流替换
                        page.Contents = pdf.make_stream(data)
        pdf.save(pdf_path)
    return stats
