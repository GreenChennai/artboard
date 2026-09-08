# ADR 0003:视觉识别 Agent 自带能力优先,本地 VQA/OCR 为备选

日期:2026-09-06 · 状态:已采纳

## 背景

本地 VQA(QORA-0.8B)与 OCR(RapidOCR)模块体积大(600MB+/110MB)且慢;
而托管 Agent 自带视觉能力,质量通常更好。

## 决策

config 新增 `vision_mode`:默认 `auto`(Agent 视觉优先);
仅当 Agent 无视觉、用户明说、或设为 `local` 时才强制本地模型。
本地模型改为**按需下载**:`scripts/fetch_model.py vqa|ocr` 从 GitHub Releases 拉取,
不再要求开箱内置。

## 后果

开箱门槛降低(不下载也能用);离线/隐私场景显式切 local。
