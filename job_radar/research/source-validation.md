# 公开来源接入验证

日期：2026-10-16。初始研究阶段仅浏览公开页面，没有调用付费搜索 API。后续真实云端测试已调用博查 12 次并使用 DeepSeek 1,894 Token，详细结果见 DEPLOYMENT.md；未登录招聘平台或投递职位。

官网补充：BOSS 搜索资料中“杭州以咏今朝信息科技”的工商信息以“以咏今朝(杭州)信息”开头；[公司网站](https://millervlogs.com/) 页尾显示“以咏今朝（杭州）信息科技有限责任公司”。已将人工核对的官网映射加入配置，官方招聘入口仍待核实。放置网络未取得充分官网证据，不能把 App Store 的发行商网站或隐私政策域名直接当成招聘公司的官网。

## BOSS 直聘

公开的 Unity 开发实习搜索页能读出标题、城市、薪资和公司：
https://www.zhipin.com/zhaopin/af25844e13c7939d3nJy3d6-/

页面出现波克城市“Unity客户端开发实习生（2027届）”的线索。打开其具体详情：
https://www.zhipin.com/job_detail/37d86b9954a0a1c90nd43t-8EFRU.html

本次跳转至安全验证页，无法确认详情及当前开放状态。因此这条只能作为“待核实线索”，不能作为已核验岗位。搜索页可能来自索引，不能用当前访问时间替代职位发布日期。

波克官网独立入口：https://www.boke.com/ ，招聘入口：https://m.boke.com/join.html 。公司官网存在不代表该岗位已获官网证实。

## 实习僧

公开详情样本：https://www.shixiseng.com/intern/inn_056cji6xw3ih

可读到索尼（中国）的 Unity 实习岗位，偏 3D 可视化/XR/交互，并非明确的游戏客户端岗位。该样本只用于验证字段解析及相关岗位分流，不默认纳入用户的主列表。是否仍可投递应在发送当次重新核验。

公司官网：https://www.sony.com.cn/ 。

反例一：https://www.shixiseng.com/intern/inn_dcbppevabzic

页面显示“当前职位已下线”，且截止时间早于当前年份，尽管仍可搜索到并展示刷新时间。首版必须识别并排除。

反例二：https://www.shixiseng.com/intern/inn_lguq63abaonj

页面带有实习标签，但正文包含多年经验要求，且截止日期已过。标签与正文冲突需要明确标记，不能仅按标题收录。

## 公司官网、SaaS 招聘与帖子

米哈游官方校园招聘入口：https://join.mihoyo.com/ 。一次直接读取失败，搜索仍返回可见内容；说明需区分“搜索可见”与“详情已读取”。

叠纸公司页：https://www.papegames.com/contactUs ，官方招聘域名候选为 career.papegames.com；应按公司官网跳转核验。

莉莉丝招聘页可出现技术美术实习，虽然要求 Unity，也不能自动归入 Unity 客户端实习主列表。

牛客内推帖子可提供原始招聘链接，但帖子发表时间、内推者描述与官方岗位状态需分别处理。

## 搜索与模型 API

博查官网 https://open.bocha.cn/ 当前跳转至 https://open.bochaai.com/ ，展示 Web Search API 与 api.bochaai.com/v1/web-search 的调用示例。此为推荐的搜索供应商候选，不代表已验证其 BOSS 岗位覆盖或已开通。

备选 Tavily 官方文档：https://docs.tavily.com/documentation/api-reference/endpoint/search ，支持限制来源域名。实际中文岗位召回率待试点比较，首版只接一种供应商。

DeepSeek 官方余额文档：https://api-docs.deepseek.com/zh-cn/api/get-user-balance/ 。建议与模型实际 Token 用量分开记录，不能将余额当作准确 Token 余额。
