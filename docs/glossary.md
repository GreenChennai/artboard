# artboard 词汇表

| 术语 | 含义 |
|---|---|
| 瘦身影子 | scaffold 默认模式:src/fonts、src/vendor 为指向 Skill 资产库的 NTFS 目录联接,项目零拷贝 |
| 联接(junction) | NTFS 目录重解析点;相对引用经 OS 穿透到 Skill 库,http/file 双通 |
| embed-fonts | `--embed-fonts`:把字体/vendor 真拷贝进项目的自包含模式(体积大,单件交付用) |
| pack | `scripts/pack.py`:穿透联接收集依赖 → 自包含 zip,HTML 引用自动改写 |
| 五问 | 开工前追问协议:用途/尺寸/风格/配色/素材(intake.md) |
| 设计简报 | 五问汇总的"生图式提示词",先给用户看再动工(design-prompt.txt) |
| 三模式 | 文案直出(A)/ 图片复刻(B)/ 换风格改配色(C)(replicate.md 为 B 的协议) |
| 复刻比对 | compare.py 生成原图 vs 复刻图并排图,逐项核对(replicate.md Step R4) |
| 风格分册 | 某视觉风格的规则集:色彩角色表+字体栈+字号阶+组件+禁则+案例(styles/) |
| 品类规范 | 某输出介质的规范:尺寸/字号下限/折线/盲区(formats/) |
| 原子混搭 | 分册章节按单关注点组织,可跨风格借用单个原子(如"瑞士版式+Y2K 配色") |
| 版权风险- | 爬虫来源素材的强制文件名前缀,交付时必须提醒更换(materials.md) |
| vision_mode | auto=Agent 视觉优先;local=强制本地 VQA/OCR(ADR 0003) |
| WPI | 渲染导出引擎:Playwright 驱动系统 Edge/Chrome,输出 PNG/GIF/MP4/PDF |
| settle | WPI 导出前的稳定化:等字体/图片、滚动触发 reveal、动画收敛到终态 |
| 孤字 | 段落末行仅 1 个汉字——排版硬禁(typography-rules.md) |
| tabular-nums | 等宽数字;数据列必须使用以垂直对齐 |
| 反 AI 味自检 | 12 条交付前清单(guardrails.md §5) |
