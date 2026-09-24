# 三剪客 · k6 负载测试 Skill

用 JavaScript 写压测脚本、一条命令发起并发流量、按阈值判定并通过退出码做性能门禁的完整操作要点。

---

## 前置条件

- 一台能装二进制的机器（Linux / macOS / Windows 官方都有构建），或者本机有 Docker
- 要压的目标地址可访问；目标是自建服务时确认压测流量不会打到生产
- 想接 CI 门禁的话，先确认流水线里能安装 k6 并能读到退出码
- 只有使用云端压测服务时才需要账号与 token；纯本地压测不需要任何 Key

---

## 使用

最短跑通路径：

```bash
k6 new                                  # 生成 script.js 骨架
# 改脚本里的目标地址、vus、duration、thresholds
k6 inspect script.js                    # 干跑一次，确认最终配置
k6 run -u 1 -d 10s script.js            # 小流量验证脚本能跑通
k6 run script.js                        # 正式压
echo $?                                 # 看退出码：0 通过，99 阈值失败
```

接 CI 时关键是**必须写阈值**：没有阈值 k6 恒退出 0，门禁形同虚设。

```bash
k6 run --summary-export=summary.json --out json=result.json script.js
```

`SKILL.md` 里有完整的最小脚本模板、stages 阶梯写法、`handleSummary` 自定义摘要、Docker 三种用法和常见坑对照表。

---

## 依赖

| 依赖 | 说明 |
|---|---|
| 运行时 | 无。k6 是单个二进制，脚本跑在它内嵌的 JS 运行时里，**不需要 Node.js** |
| 安装方式 | apt / dnf / Homebrew / choco / winget / MSI / Docker 镜像 / Release 压缩包 |
| Docker | 仅在用容器方式运行时需要；容器内看不到宿主机文件，脚本要么挂载要么走 stdin |
| Go 工具链 | 仅在使用 xk6 自建带扩展的二进制时需要（也可用官方 xk6 Docker 镜像绕过） |
| 外部存储 | 仅当用 `--out` 推指标时需要，如 Prometheus、InfluxDB、Datadog 等 |
| 网络 | 压测本身要联网；包管理器安装与推指标也需要 |

---

## 安全

- 不内嵌任何密钥：脚本里的 token、地址一律通过 `-e` 或环境变量传入，不要硬编码进压测脚本
- **压测等于一次小规模压测攻击**：先确认目标是你有权压的系统，压测前知会相关方，别对生产环境或第三方站点直接开压
- 并发量与时长要逐步升，先单 VU 验证脚本正确性，避免脚本写错把目标打挂
- `K6_CLOUD_TOKEN` 等凭证只放在 CI 的 secret 里，不要写进脚本或提交进仓库
- 压测会真实产生业务数据（下单、注册、发消息），跑完记得清理，别污染生产库
- `handleSummary` 与 `--out` 写出的报告可能包含目标 URL 与请求细节，归档时注意脱敏

---

## 上游项目

本 Skill 由 **三剪客** 出品并独立编写，正文为原创内容，不包含第三方项目的源代码。

- 项目：`k6`
- 仓库：https://github.com/grafana/k6

---

## 许可证

MIT，见 `LICENSE.md`。

---

---

## 联系我们

- **技术微信：9872659** —— 加好友时说一下是从哪个 Skill 找过来的，直接给你配套的 API Key 与能跑的示例。
- **要算力 / 要 API Key**：[算力集市 · 注册领 API Key](https://api.a7w.cn/) —— 一个 Key 调用全部 AI 算力，注册、充值、创建 Key 都在这里。
- **更多 AI 插件与接口**：[AI 插件市场](https://aigc.a7w.cn/)。

---

## 相关链接

| 链接 | 地址 | 说明 |
|---|---|---|
| [算力集市 · 注册领 API Key](https://api.a7w.cn/) | api.a7w.cn | 一个 Key 调用全部 AI 算力；注册、充值、创建 Key 都在这 |
| [AI 插件市场](https://aigc.a7w.cn/) | aigc.a7w.cn | 浏览全部 AI 插件与接口说明 |
| [三剪客 · 一句话批量出片](https://ks.a7w.cn/) | ks.a7w.cn | 短剧二创 / 影视解说 / 矩阵号批量混剪桌面客户端 |
| [视频超清 · 在线批量超分](https://vr.a7w.cn/) | vr.a7w.cn | 网页版视频超分，批量处理，最高 4K |
| [0人公司 · AI Agent 平台](https://a7w.cn/) | a7w.cn | 主站，了解整套 AI Agent 生态 |
