# 部署验证记录

日期：2026-10-16（Asia/Shanghai）。

- 仓库：https://github.com/Ash-final-light/EmailSender
- 当前仓库可见性：公开，保持原设置。源码及公开新闻候选可见，凭据和收发件地址仅存储于 Actions Secrets。
- 模型：DeepSeek 官方接口，deepseek-flash；已实际读取模型列表并生成中文周报。
- 已配置 Secret 名称：DEEPSEEK_API_KEY、SMTP_USER、SMTP_PASSWORD、MAIL_TO。未在本文件记录值。
- 发信服务：已按用户选择切换为 QQ 邮箱；发件与收件使用同一个用户指定地址，地址仅保存于 Secrets。SMTP_HOST=smtp.qq.com、SMTP_PORT=465、SMTP_SECURITY=ssl 已配置为 Repository Variables。
- QQ 邮箱 SMTP 授权码已由账号持有人配置；首次实际登录和 SMTP 提交成功。
- 三个工作流已部署并处于 active：Checks、Collect News、Game Tech Weekly。

## 已实际验证

1. 本地和 GitHub Ubuntu 环境的 14 项单元测试通过。
2. 云端 24/24 个配置入口读取成功，本轮获得 358 条近七天候选。入口可读不代表该来源本周有新条目。
3. 云端预览生成 12 条中文资讯，HTML 保存为 weekly-preview Artifact。
4. 预览流程未发送邮件，发送历史未因预览而更新。
5. 采集后的候选与来源状态已经由 Actions 自动提交到默认分支。
6. 在进入模型前为每个来源限制最多 3 条候选，减少来源集中；模型输出仍校验原始 ID、中文、长度、类型和数量。
7. 已停用验证失败的直接 RSS，使用可用的官方/媒体定向检索入口补充发现；不是全站抓取或全文阅读。
8. 首次真实发送任务完成并成功；QQ SMTP 接受包含 12 条资讯的邮件，提交时间为北京时间 2026-10-16 20:30:46，统计区间为 2026-10-09 至 2026-10-16。
9. 发送前的状态检查点和发送后的历史均成功提交至默认分支；outbox 状态为 sent，已发送历史记录为 12 条。本轮 24/24 个来源入口可用。

验证入口：

- 测试通过：https://github.com/Ash-final-light/EmailSender/actions/runs/38898161914
- 预览成功：https://github.com/Ash-final-light/EmailSender/actions/runs/38898165388
- 密钥配置：https://github.com/Ash-final-light/EmailSender/settings/secrets/actions
- 首次真实发送成功：https://github.com/Ash-final-light/EmailSender/actions/runs/38900939692

首轮预览因模型选取过多同一来源条目而被严格校验拒绝，未发送邮件。后续修复已通过新的云端预览验证。Actions 页面保留首次失败记录，这是正常的部署调试历史。

## 后续观察

首次真实发送已经完成，不需要再次运行 send 进行重复测试。收件人可在 QQ 收件箱或垃圾箱中确认邮件及中文显示。

已验证 QQ SMTP 登录与服务接受投递；不等同于确认邮件进入收件箱。每天 08:00/20:00 与每周一 09:00 的定时规则已配置，但尚未观察首个自然定时周期。

本轮样报中 Unity 专属技术资讯较少，采用其他引擎、.NET、开发工具和行业内容补充，未编造 Unity 更新。后续按每周实际质量调整来源和关键词。
