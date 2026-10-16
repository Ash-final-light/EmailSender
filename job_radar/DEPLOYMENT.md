# 部署记录

2026-10-16，部署在现有公共仓库 Ash-final-light/EmailSender 的 `job_radar/` 子目录。岗位状态独立，复用 Secrets。

- 本地原周报 14 项测试通过，岗位雷达 22 项测试通过；[最新云端 Checks](https://github.com/Ash-final-light/EmailSender/actions/runs/38906682189) 同样全部通过。
- [首轮云端 Checks](https://github.com/Ash-final-light/EmailSender/actions/runs/38905756492) 成功（当时岗位测试 21 项，之后增加官网映射缓存更新测试）。
- [真实搜索与模型预览](https://github.com/Ash-final-light/EmailSender/actions/runs/38905771115) 成功：12 次博查搜索，26 条搜索结果，4 个具体岗位 URL；2 个实习僧岗位明确已下线被排除，2 个 BOSS 详情受限保留为待核实线索。主栏可核验匹配岗位 0 条。
- 真实 DeepSeek 用量：输入 1461、输出 433，共 1894 Token，周软预算 50000。未触及额度暂停，没有提高预算。
- 首轮检查 7 家公司官网与招聘入口；多家招聘页为动态页面，米哈游招聘页访问失败。入口访问不等于发现有效岗位。
- 预览经浏览器检查，中文字段和链接可见。以咏今朝的公司官网经人工对应主体后加入配置，放置网络官网待核实。
- `JOBS_SCHEDULE_ENABLED` 尚未设置为 true。样报确认后再开启每天 08:30 采集、周二/五 09:00 发信。

首封真实样报已完成：[发信工作流](https://github.com/Ash-final-light/EmailSender/actions/runs/38906685618) 成功，QQ SMTP 接受，`outbox.json` 状态为 sent，时间为北京时间 2026-10-16 21:17:29，发送历史 2 条。邮件主栏 0 条、待核实线索 2 条，并包含公司官网和七家公司招聘入口。发信复用当日缓存，新增搜索请求 0，新增模型调用 0；累计模型用量仍为 1894 Token。实际收件箱落点和显示由用户确认。
