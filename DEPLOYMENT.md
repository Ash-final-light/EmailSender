# 部署验证记录

日期：2026-10-16（Asia/Shanghai）。

- 仓库：https://github.com/Ash-final-light/EmailSender
- 当前仓库可见性：公开，保持原设置。源码及公开新闻候选可见，凭据和收发件地址仅存储于 Actions Secrets。
- 模型：DeepSeek 官方接口，deepseek-flash；已实际读取模型列表并生成中文周报。
- 已配置 Secret 名称：DEEPSEEK_API_KEY、SMTP_USER、MAIL_TO。未在本文件记录值。
- 尚缺：SMTP_PASSWORD，即指定 Gmail 的应用专用密码。
- 三个工作流已部署并处于 active：Checks、Collect News、Game Tech Weekly。

## 已实际验证

1. 本地和 GitHub Ubuntu 环境的 14 项单元测试通过。
2. 云端 24/24 个配置入口读取成功，本轮获得 358 条近七天候选。入口可读不代表该来源本周有新条目。
3. 云端预览生成 12 条中文资讯，HTML 保存为 weekly-preview Artifact。
4. 预览流程未发送邮件，发送历史未因预览而更新。
5. 采集后的候选与来源状态已经由 Actions 自动提交到默认分支。
6. 在进入模型前为每个来源限制最多 3 条候选，减少来源集中；模型输出仍校验原始 ID、中文、长度、类型和数量。
7. 已停用验证失败的直接 RSS，使用可用的官方/媒体定向检索入口补充发现；不是全站抓取或全文阅读。

验证入口：

- 测试通过：https://github.com/Ash-final-light/EmailSender/actions/runs/38898161914
- 预览成功：https://github.com/Ash-final-light/EmailSender/actions/runs/38898165388
- 密钥配置：https://github.com/Ash-final-light/EmailSender/settings/secrets/actions

首轮预览因模型选取过多同一来源条目而被严格校验拒绝，未发送邮件。后续修复已通过新的云端预览验证。Actions 页面保留首次失败记录，这是正常的部署调试历史。

## 下一项验收

账号持有人将 Gmail 应用专用密码填入 SMTP_PASSWORD 后，运行 Game Tech Weekly，mode = send。

实际 SMTP 登录、Gmail 到 QQ 的投递和收件箱显示仍待验证，不能视为已发信成功。每天 08:00/20:00 与每周一 09:00 的定时规则已配置，但尚未等待首个自然定时周期。

本轮样报中 Unity 专属技术资讯较少，采用其他引擎、.NET、开发工具和行业内容补充，未编造 Unity 更新。后续按每周实际质量调整来源和关键词。
