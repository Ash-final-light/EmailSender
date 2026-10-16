# 开发者视野 · 游戏开发与互联网中文周报

按个人兴趣收集多个公开来源，使用 **DeepSeek** 筛选和归纳，再通过 SMTP 向配置的收信邮箱发送中文周报。当前部署使用 QQ 邮箱发信；也支持 Gmail 等服务。默认 Unity 为主，兼顾其他引擎、国内外互联网与 AI 开发工具。

实际部署和云端验证状态见 [DEPLOYMENT.md](DEPLOYMENT.md)。云端预览与首次真实 SMTP 发信已通过，QQ 发信服务接受了包含 12 条资讯的邮件；收件箱实际显示由收件人确认。

新增独立子项目：[Unity 实习岗位雷达](job_radar/README.md)，检索全国 Unity 客户端实习岗位并生成中文邮件，复用凭据，使用独立预算和发送状态。首次样报确认前，岗位雷达的定时任务保持关闭。

## 自动运行

- 每天北京时间 **08:00、20:00** 收集并保存候选资讯，不调用模型、不发邮件。
- 每周一北京时间 **09:00** 开始生成并发送过去七天的精选。
- 目标 10–16 条，不凑数；游戏开发 / 互联网与 AI / 游戏行业默认倾向为 50% / 35% / 15%。
- 使用 UTC cron，对应 Asia/Shanghai；GitHub 定时任务可能延迟，首次实际定时运行仍需观察。
- 工作流共享并发锁；候选保留 30 天（最多 4000 条），已发送 URL 哈希保留 90 天。
- 数据保存到仓库默认分支，电脑不需要一直开机。

## 部署与凭据

仓库需要允许 Actions 运行和工作流写入仓库。已存在的 Actions Secrets 不会被代码读取或回显。

在 Settings → Secrets and variables → Actions → Repository secrets 配置：

| Secret | 用途 |
| --- | --- |
| DEEPSEEK_API_KEY | DeepSeek 官方 API Key |
| SMTP_USER | 发信邮箱完整地址（当前部署为 QQ 邮箱） |
| SMTP_PASSWORD | 发信服务授权码；QQ 邮箱填写 SMTP 授权码，不是 QQ 登录密码 |
| MAIL_TO | 收信邮箱；多个收件地址用英文逗号分隔 |

QQ 邮箱：账号持有人登录 [QQ 邮箱](https://mail.qq.com/)，进入设置 → 账户，找到包含 SMTP 的服务项目，按页面提示完成安全验证、开启服务并生成授权码。将授权码直接填入 SMTP_PASSWORD Secret，无需提交到代码或聊天。具体验证方式以账号页面为准；帮助见 [QQ 邮箱帮助中心](https://service.mail.qq.com/)。

如以后改回 Gmail，填写 Gmail 应用专用密码，并将 SMTP_HOST 改为 smtp.gmail.com；见 [Google 官方说明](https://support.google.com/accounts/answer/185833)。

可选 Repository Variables：

| Variable | 当前部署值（脚本未设置变量时的兼容默认值） |
| --- | --- |
| LLM_MODEL | deepseek-flash |
| SMTP_HOST | smtp.qq.com（未配置时脚本默认 smtp.gmail.com） |
| SMTP_PORT | 465 |
| SMTP_SECURITY | ssl；也支持 starttls |

模型默认依据 DeepSeek 官方文档与实际模型列表选择，使用 JSON 输出模式、关闭思考模式、进行本地字段校验；格式错误最多重新生成一次。SDK 保留短暂网络故障重试，认证或余额问题不自动更换模型或平台。

接口固定为 DeepSeek 官方 HTTPS 域名，原 OpenAI Key 不会发送到 DeepSeek。

## 首次运行

1. Actions → **Checks**：确认单元测试通过。
2. Actions → **Game Tech Weekly** → Run workflow，mode 选 **preview**。
3. 下载该次运行的 **weekly-preview** Artifact，打开 report-preview.html；此模式收集候选但不发送邮件、不修改发送历史。
4. 确认四个 Secrets 都已配置后，再选择 mode = **send** 发送第一封真实邮件。
5. 在收信邮箱确认中文标题、正文、原文链接以及是否进入垃圾箱。SMTP 接受消息只说明服务接受投递，不代表已进入收件箱。

## 信息源

config.json 管理公开 RSS、Google News 中英文检索及 GitHub Releases。

- 直接源：Hacker News（经第三方 hnrss.org）、Godot 官方、.NET 官方、The Game Business。
- 新闻检索：Unity、国内外互联网、AI 工具、其他引擎、游戏行业，并有 Unity 官网、36氪、Game Developer 的定向查询。
- Releases：YooAsset、HybridCLR、VContainer、UniTask、Netcode、Unity ECS/Graphics、Godot。
- 本轮直接 RSS 验证中，36氪返回 HTML，Unity 入口不可用，Game Developer 返回拒绝访问；已停用这些直接入口，改用发布方定向检索。并不代表已抓取这些网站全文。
- 来源可用不表示当周一定有相关内容；邮件注明来源读取成功比例，部分失败时提醒覆盖不足。
- 每条保留真实 URL 和发布时间，并标注“基于来源摘要”或“Release 说明”。当前不抓取文章全文，中文解释的深度受来源摘要限制。
- 聚合链接可能先进入 Google News。没有 Release 的仓库更新不在 Releases API 覆盖范围。

## 本地运行

需要 Python 3.11 或更新版本。Windows 包含 tzdata 依赖。

    py -3.13 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt

通过终端环境变量配置凭据；.env.example 只作字段参考，程序不自动加载 .env。

    python main.py --collect-only
    python main.py --preview --offline
    python -m unittest discover -s tests -v

--preview 不写候选池、发送历史或发件箱；--offline 复用已采集的数据。默认直接运行 main.py 也是只生成预览。

正式发送由 Actions 分步骤完成：

    python main.py --check-config
    python main.py --prepare
    python main.py --reserve-send
    # 此时必须先将 data/ 持久化，再执行 SMTP
    python main.py --deliver

## 发送状态与恢复

data/outbox.json 记录 prepared → attempting → sent。工作流在 SMTP 前把 attempting 状态提交到仓库，SMTP 完成后再提交发送历史。

- 发送出错时写 uncertain，不自动重复投递；进程在发送期间中断时，仓库可能保留 attempting。
- 再次发送会拒绝覆盖 prepared、attempting 或 uncertain，避免直接重跑导致重复邮件。
- 如果发送成功但最终状态提交失败，仍需人工核对收信情况；本项目不保证 SMTP 的严格“恰好一次”投递。
- 人工核对后，运行 python main.py --confirm-delivered 将已收到的报告计入历史；确认需要放弃后运行 python main.py --release-delivery。将恢复后的 data/ 提交到默认分支。释放未知投递状态可能导致下一次重复，应先核对邮箱。
- 历史去重基于 URL 与同批相似标题，模型另做同批事件筛选；跨周不同 URL 的同一事件仍可能重复。

## 文件与隐私

源码和公开新闻数据会进入当前仓库。若仓库为公开，候选、摘要、来源状态也可公开查看；密钥、收发件地址通过 Secrets 注入，不写入新闻数据。工作流不输出密码、HTTP 错误正文或 SMTP 详细响应。

PROTOTYPE.md 是先前的产品设计记录，prototype/email.html 是标注为示例的静态样稿；实际邮件由 main.py 根据采集结果生成。正式预览保存在 Actions Artifact，本地 report-preview.html 不提交。

本项目没有注册新账号、购买服务或改变仓库可见性。
