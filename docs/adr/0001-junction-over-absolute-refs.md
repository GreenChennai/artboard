# ADR 0001:项目资产引用用 NTFS 目录联接,不用 file:/// 绝对路径

日期:2026-09-06 · 状态:已采纳

## 背景

海报项目需要引用 Skill 库内字体/vendor,而项目要与 Skill 分离存放。
初版用 file:/// 绝对路径引用,实测失败:WPI 经 http:// 静态服务加载页面,
Chromium 安全策略**禁止 http 页面加载 file:/// 副资源**,字体全部回退。
次选方案(每项目拷贝字体)导致单项目 500MB+。

## 决策

scaffold 默认把 `src/fonts`、`src/vendor` 建为**指向 Skill 资产库的 NTFS 目录联接**
(PowerShell `New-Item -ItemType Junction`,路径经环境变量传递)。
HTML 一律用相对引用 `fonts/<款>/<文件>`,OS 层穿透到 Skill 库。
交付迁移用 `scripts/pack.py`:穿透联接收集真实文件进 assets/,HTML 引用改写为相对路径。

## 后果

- 批量制作零拷贝;删除项目不影响 Skill 库;
- 联接创建的 cmd 子进程在本机出现"无效开关"解析怪癖 → 已换 PowerShell 方案;
- **rm -rf 联接目录的行为取决于工具**(MSYS rm 不穿透,实测库无损),pack.py 是安全出口;
- `--embed-fonts` 保留为自包含选项;
- 旧项目/联接失败残留的实体目录用 `scripts/slim_project.py` 一键转联接。
