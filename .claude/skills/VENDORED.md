# 第三方 skill 来源登记

升级前先读完新版本（profile 1.2g），不要直接覆盖本地改过的版本。

| skill | 上游 | 提交 | 许可证 | 引入日期 | 本地改动 |
|---|---|---|---|---|---|
| guizang-ppt-skill | github.com/op7418/guizang-ppt-skill | 早于 93d21bf | AGPL-3.0 | 2026-05-19 | 2026-09-01 按 hub-and-spoke 拆分（hub 193 行，拆出 step1/step3）。上游 93d21bf 已到 636 行、新增演讲者模式与共享设计系统，**未合并**，升级需重新拆分 |
| guizang-page-skill | github.com/op7418/guizang-pages-skill | bb39103 | AGPL-3.0 | 2026-10-31 | 无 |
| guizang-social-card-skill | github.com/op7418/guizang-social-card-skill | 64d02d4 | AGPL-3.0（另有商业授权说明） | 2026-10-31 | 无 |
| humanizer-zh | github.com/op7418/Humanizer-zh | f4518a8 | MIT | 2026-10-31 | 无 |

经由 op7418/dsh-guizang-design（DeepSeek Harness 插件，2398333）获取。插件本体（作品库、语气档案 guizang-voice）依赖 dsh 主进程工具，**不可移植，未安装**。

**许可证提示**：AGPL-3.0 的三个 skill 用于自己生产内容没有问题；若把它们做进给别人用的产品或服务，需看作者的商业授权说明（guizang-social-card-skill/COMMERCIAL_LICENSING.md）。
