# 三剪客 · HTML 转视频引擎 Skill

用 HTML/CSS 描述时间轴，一条命令产出结果可复现的 MP4。

---

## 前置条件

- Node.js **22 及以上** 版本；低于此版本无法启动。
- PATH 中需要有 FFmpeg 与 ffprobe。
- 准备一个空目录当工程根；第一次运行要联网拉取 `hyperframes` 包，并获取固定版本的 Chrome。
- 若要求跨机器逐字节一致，还需要一个可用的 Docker。

建议先跑体检，再开始动手：

```bash
npx hyperframes doctor          # 输出给人看
npx hyperframes doctor --json   # 输出给机器看：退出码恒为 0，需自行判读 payload 里的 ok
npx hyperframes browser ensure  # 缺少 Chrome 时补齐
```

---

## 使用

最小可用流程共三步：

```bash
npx hyperframes init my-video
cd my-video
npx hyperframes preview --background --port 3017   # 在浏览器里实时预览并编辑时间轴
npx hyperframes lint                               # 编写过程中随手检查
npx hyperframes check                              # 交付前的最终质量关卡
npx hyperframes render --quality high --output out.mp4
```

把文案抽成变量后，同一套模板就能批量产出多条：

```bash
npx hyperframes render --batch rows.json --output "renders/{name}.mp4" --strict-variables
```

下面三条是硬约束，务必遵守：

1. 动画状态只能从时间值推导；时钟、随机数、渲染期发起的网络请求一律禁止。
2. 所有 `<video>` / `<audio>` 都必须带 `id`，且都不得写 `crossorigin`。
3. 根元素上的 `data-duration` 在编译期就被读取，属于常量；要改长度就得改根元素本身。

完整步骤、`data-*` 属性全表与批量出片排错，见 `SKILL.md` 的「工作流路由」。

### 配音：写旁白稿 + 分段合成（可选）

成片要人声旁白时，不用另外找工具，也不用自己录。`scripts/run.py` 接 [api.a7w.cn](https://api.a7w.cn/)：
大模型写旁白稿，`voice_tts` 分段配音，产出能直接塞进 `<audio>` 的音轨与 `cues.json`。
需要你自己的 API Key，**不跑就不联网、不产生费用**。

```bash
export A7W_API_KEY=sk-xxxx                      # Windows: set A7W_API_KEY=sk-xxxx
python3 scripts/run.py dub \
    --topic "新品上线第一天" --seconds 20 --cues 4 \
    --script narration.md --outdir audio --voice <reference_id>
```

产出 `narration.md`、`audio/cue-01.mp3`…、`audio/cues.json`（含每段真实秒数）。
把秒数填进对应 clip 的 `data-duration`，每个 `<audio>` 记得绑唯一 `id`。
端点与参数细节见 `SKILL.md` 的「怎么用（命令行）」。

---

## 依赖

| 依赖 | 必需性 | 说明 |
|---|---|---|
| Node.js 22+ | 必需 | 命令行工具与渲染管线都依赖它 |
| FFmpeg / ffprobe | 必需 | 负责帧编码与成片校验；`run.py` 检测到 ffprobe 时会顺便读取音频时长 |
| 固定版本 Chrome | 必需 | 由 `browser ensure` 自动获取；锁定版本是为了让像素输出可复现 |
| Docker | 可选 | 只有走 `render --docker` 这条可复现渲染路径时才需要 |
| Python 3.8+ | 可选 | 只有 `scripts/run.py`（旁白与配音）用得到；仅用标准库，无需安装任何包 |
| 网络 | 首次必需 | 拉包与安装 registry 条目都要联网；合成中引用的外部 CDN 脚本也会在渲染时去取；执行 `run.py` 时会请求 `api.a7w.cn` |

---

## 安全

- 包内不含任何密钥、Token 或账号。
- 旁白与配音（`scripts/run.py`）需要**你自己的** api.a7w.cn API Key，由你通过 `--key`、
  `A7W_API_KEY` 或 `~/.a7w/config.json` 提供；脚本只把 Key 放进请求头，不落盘、不外传。
  不跑这段就完全不联网、不产生任何费用。
- 本地渲染不需要任何凭据；`publish` 与 `cloud` 采用 OAuth，令牌由 CLI 自己存放在用户目录，本 Skill 既不读取也不转存。
- 不代为转发用户请求，也不经手用户数据。
- 渲染过程中会真实拉起子进程（无头 Chrome 与 FFmpeg），并可能常驻一个后台 Studio 服务；不再使用时请显式关闭：`npx hyperframes preview --stop`。
- 合成中引用的外部脚本与素材会在渲染阶段被下载；若工程涉密或位于内网，请先把依赖本地化。
- 批量渲染所用的 `rows.json` 与 `--variables-file` 可能含有业务敏感字段，请自行限定文件范围与权限。

---

## 版权

本 Skill 由 **三剪客** 独立编写并出品，正文均为原创，不含任何第三方项目的源代码。

渲染引擎属于社区开源命令行工具，由 `npx` 按需拉取；本包不携带其源码，
与该工具维护方之间不存在隶属、代理或背书关系。`scripts/` 下的 Python 脚本由本包自行编写。

---

## 许可证

MIT，见 `LICENSE.md`。

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
