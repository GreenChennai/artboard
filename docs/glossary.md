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
| 证据链 | 复刻纪律:每个颜色/度量追溯到测量;token 必须带采样证据,裸眼估的不进 CSS(replicate.md) |
| 分区普查 | inspect_ref.py census 按区采样:flat fills=真填充/all pixels=小块/ink core=文字墨色(R1b) |
| 复刻比对 | compare.py 生成原图 vs 复刻图并排图(--region 局部放大+ΔRGB 数字),逐分区核对(replicate.md Step R4) |
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
| 矢量枢纽 | HTML 先打印成 Chromium 单页矢量 PDF,再衍生 SVG/EPS/转曲 PDF(ADR 0006) |
| 转曲(outline) | 文字变字形轮廓路径;矢量交付产物一律转曲,防换机换字体走样(ADR 0007) |
| -print.pdf | Chromium 原生打印 PDF:文字内嵌可编辑,AI 打开可改字(需装同款字体) |
| -outline.pdf | ghostscript 转曲 PDF:任何机器视觉一致,文字不可选 |
| AI 兼容 PDF | Illustrator 可直接打开编辑的 PDF;真 .ai = 在 AI 里打开它另存一次(ADR 0008) |
| SSIM 验收 | 转换产物栅格化后与基准截图算结构相似度,≥0.95 合格 ≥0.99 优秀(vector-export.md) |
| 矢量安全清单 | 16 种 CSS 原语转换实测表;硬切透明渐变/blend-mode/渐变字三条禁令 |
| WebHtml2VectorEdit | 自写正向转换核心:HTML→分层 AI 可编辑 PDF/SVG/EPS,不依赖 WPI |
| VectorEdit2WebHtml | 自写逆向核心:PDF/EPS/SVG/.ai → 可维护 HTML(visual/editable 双模式) |
| OCG | PDF 可选内容组;ai.pdf 的图层载体,Acrobat/浏览器可开关 |
| 蒙层 | 图片之后的同级渐变遮罩,单独成层保证盖在照片上 |
| 面板底色克隆 | 分层手术:有底色又含内容的元素,底色剥离进图形层,本体转结构 |
