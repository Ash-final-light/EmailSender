# Unity 实习岗位雷达

EmailSender 仓库中的独立子项目：全国检索 Unity 客户端实习岗位，每周两封中文邮件。复用现有 DeepSeek 与 QQ SMTP Secrets；候选、去重历史、额度和发送状态全部保存在 `job_radar/data/`，与技术周报独立。

## 运行范围

- 博查 Web Search：BOSS直聘、实习僧、牛客，以及公司官方招聘站的 12 组查询。搜索结果只是线索。
- 官网优先：米哈游、叠纸、腾讯、网易游戏、莉莉丝、波克城市、索尼中国的预设官网/招聘入口。可以在 `config.json` 增加来源。
- 公开详情：读取配置域名内可公开访问的 HTML / JobPosting JSON-LD。动态页面、登录和安全验证受限时降为待核实，不绕过验证。
- 只将有明确实习、Unity、客户端证据且近期可读、未发现关闭或过期提示的岗位放入主栏。技术美术、纯UE、社招正式岗等不补入主栏。
- 事实字段逐字摘录并再次校验，薪资保留原单位。缺失字段和未知公司官网标为待核实；模型不生成域名。
- “已核验”指当前可读资料，不能保证岗位仍接受投递。首次发现不是发布日期，毕业届别和出勤条件供用户自行判断。

目前没有全站抓取能力；官网动态页和搜索索引覆盖限制可能使匹配岗位为零。预设公司域名还会显示本次访问状态，不能把预设映射当成自动验证过的招聘主体。

## 配置与定时

在现有 Secrets 基础上新增 `BOCHA_API_KEY`。需要的 Secrets 共五个：`BOCHA_API_KEY`、`DEEPSEEK_API_KEY`、`SMTP_USER`、`SMTP_PASSWORD`、`MAIL_TO`。QQ 授权码不用重新配置。

工作流 **Unity Internship Radar** 支持手动运行，默认 `preview`。定时运行受 Repository Variable `JOBS_SCHEDULE_ENABLED=true` 控制；首次样报确认前保持关闭。

开启后，每天北京时间 08:30 采集，周二和周五 09:00 生成并发信。GitHub cron 可能延迟。无新增或变化时仍发简短状态邮件。相同岗位的事实与状态未变化则不重复提醒；不能仅因 AI 换种说法而重复。

## 调用与额度

默认每天最多 12 次搜索、40 次公开页面检查；每次生成最多 2 次模型请求，每次最多输出 5000 Token，本周模型软预算 50000 Token。模型沿用仓库 `LLM_MODEL`，未设置时为 `deepseek-flash`。

付费调用前先持久化预留量，成功后按接口返回的真实 Token 结算；超时且未知计费时保留预留。字符长度加最大输出用于保守估计，属于软预算，不是服务商账单或余额。API 错误、搜索上限、模型预算触发持久化暂停，发一封不调用 AI 的固定模板提醒，等待人工确认。页面检查达到上限只停止更多详情读取，未读取的页面不冒充已核验。

暂停不会因跨天或跨周自动解除。确认额度/充值/预算后，手动运行 `resume`，可选填 `weekly_token_limit` 调整当周预算；不会清空历史用量。随后再运行 `preview` 或 `send`。不自动充值、不更换付费平台、不无限重试。提醒邮件自身投递失败时，Actions 失败记录和仓库暂停状态仍保留，需要人工查看。

## 手动运行与恢复

```powershell
python -m pip install -r job_radar/requirements.txt
python -m unittest discover -s job_radar/tests -v
python -m job_radar.app preview
python -m job_radar.app preview-cached
python -m job_radar.app send
```

`preview` 会采集、归纳并生成 `artifacts/jobs-preview.html` 和同名 JSON，不发送常规简报、不修改发送历史；付费调用仍计入预算，额度受限时仍发送提醒。`preview-cached` 跳过搜索和页面访问，但仍可能归纳未处理候选。`preview-seeds` 只检查有限测试种子，不能当成全网搜索结果。

云端可在 Actions 下载 **unity-internship-preview** Artifact。持久状态写回默认分支；与原周报共享并发锁避免同时提交冲突。仓库保持现有公开状态，采集的是公开岗位资料；凭据仅在 Actions Secrets 中。

发送状态为 `prepared → attempting → sent`。SMTP 前先把 `attempting` 持久化，结果不明写为 `uncertain` 并阻止自动重发。SMTP 接受不代表已进入收件箱。先核对实际收信，再用 `confirm-delivered` 确认或 `release-delivery` 放弃旧记录；不要盲目重跑。重发由用户核对后执行。

`DESIGN.md` 保存最初方案，`prototype/` 是静态风格样例，真实报告以 Actions Artifact 和当前代码为准。
