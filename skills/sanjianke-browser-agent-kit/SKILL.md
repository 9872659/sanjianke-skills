---
name: sanjianke-browser-agent-kit
slug: sanjianke-browser-agent-kit
displayName: 三剪客 · 浏览器自动化
description: "让 AI Agent 真正操作浏览器：打开页面、点按、填表、翻页、抓取、截图、下载，并保持稳定可控。 遇到问题可加技术微信 9872659。"
version: 1.0.1
summary: "从会话/页面/元素定位/等待策略的地基讲起，给出定位器优先级与降级链、等待与重试的量化参数、截图与 DOM 取值的分工，并明确登录态管理、验证码与反爬的合规边界；附三份资料覆盖选型、稳定性写法与安全排错。 遇到问题可加技术微信 9872659。"
license: MIT
tags:
  - 三剪客
  - AI Agent
  - 浏览器自动化
  - RPA
---

# 三剪客 · 浏览器自动化

让 AI Agent 真正操作浏览器：打开页面、点按、填表、翻页、抓取、截图、下载，并保持稳定可控

Agent 操作浏览器这件事，难的不是「点得到」，而是「明天还点得到」。页面上线一次改版、按钮文案改一个字、列表多一层懒加载，写死的选择器就集体失效，任务在半路断掉，而且断在什么状态你都说不清。

这份规范把浏览器自动化拆成三层来管：**会话层**（进程、上下文、页面、标签页谁是谁）、**定位层**（怎么选元素才不容易失效、失效了按什么顺序降级）、**判定层**（怎么确认「这一步真的成了」，而不是睡了三秒就当成功）。三层都给出可执行的方法、选项名和量化阈值，你可以直接照着写，也可以只挑稳定性和安全两章改造已有脚本。

同时它把红线写在明处：只操作已获授权的站点，不提供任何验证码绕过、指纹伪装、风控对抗或限流规避手段。遇到登录墙、验证码、频控，正确动作是停下来交回给人或走站点官方接口，而不是加大力度重试。

## 权限与用途说明

| 能力 | 是否申请 | 用途 |
|---|---|---|
| 网络访问 | 是（必需） | 驱动真实浏览器访问你指定的目标站点，加载页面、接口请求、静态资源；回传页面内容与截图。访问范围应由使用者给定的白名单限定 |
| 读取文件 | 视需要 | 读取登录态存档（`storageState` / 用户数据目录）、待处理 URL 或任务清单、上传用的本地文件、页面基线快照 |
| 写入文件 | 视需要 | 落盘截图、导出 HTML/文本、保存下载文件、把登录态存档与运行日志写到工作目录 |
| 凭证 | 是（常见） | 登录态存档内含 Cookie 与本地存储，等价于账号凭证；账号密码必须从环境变量或密钥管理读取，禁止硬编码进脚本、配置与提交记录 |
| 子进程 / 后台常驻 | 是（必需） | 拉起浏览器进程（Chromium / Firefox / WebKit 内核）；长任务与批量队列需要后台常驻，并保证异常退出时释放浏览器进程 |

**凭证与责任**：本 Skill 是一份作业规范，不内嵌任何密钥、Token、Cookie，不代理转发你的请求，也不代收任何费用。你跑出去的每一个请求、每一个账号动作都记在你自己的名下，请确保目标站点已获授权、账号操作符合站点条款与当地法规。登录态文件按凭证对待：加进 `.gitignore`、设最小文件权限、到期即删，不要随日志或产物一起打包外发。

## 触发场景

- 「帮我登录后台，把上个月的对账单下载下来」——登录态 + 按条件筛选 + 下载落盘。
- 「这个页面上的表格要导出成 Excel / CSV，翻页都要」——表格取值 + 翻页终止条件 + 字段对齐。
- 「每天上午自动去这个站查一次价格，变了就记下来」——定时任务、幂等、变更检测与失败告警。
- 「这个后台要填 30 条数据，一条条点太慢了」——批量填表、提交后校验、失败项单独重试。
- 「上次写的脚本前天突然报元素找不到，帮我看为什么」——定位器失效诊断与降级链重写。
- 「点完之后什么都没有发生，截图也是空白的，到底哪一步错了」——等待语义与可观测性排查。
- 「这个站有图形验证码 / 滑块，能不能自动过」——**不能**，走合规路径：官方 API、人工介入或申请授权。
- 「页面要截图给多模态模型看，让它自己决定点哪里」——ARIA 快照 / 图像双通道取值与动作回填。

## 快速开始

### 第 0 步：先把环境装起来

```bash
# Node 路线
npm i -D playwright
npx playwright install chromium          # 只装用得到的那个内核，别全下
npx playwright --version

# Python 路线
pip install playwright
python -m playwright install chromium
```

首次跑通前先做一次「环境自检」，确认不是环境问题：

```bash
npx playwright install --dry-run          # 看内核是否已就位
npx playwright --version
node -e "console.log(process.version)"    # 需要 Node 18+
```

### 路径一：最小闭环（先验通，再谈稳定）

```javascript
// smoke.mjs —— 一个页面、一次定位、一次取值、一次截图
import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();

await page.goto('https://example.com', { waitUntil: 'domcontentloaded', timeout: 30000 });

// 定位用 role + 可访问名，不用结构路径
const heading = page.getByRole('heading', { level: 1 });
await heading.waitFor({ state: 'visible', timeout: 10000 });   // 先确认存在且可见
console.log('H1 =', (await heading.innerText()).trim());

await page.screenshot({ path: 'out/smoke.png', fullPage: true });
await browser.close();
```

跑通的判据是：**退出码 0 + 截图非空白 + 打印出真实标题**。三者缺一，先修链路，不要继续写业务流程。

### 路径二：定位与等待的稳定写法（可直接抄的骨架）

```javascript
const CANDIDATES = [
  (p) => p.getByRole('button', { name: /^提交$/ }),          // 1 语义
  (p) => p.getByTestId('submit-btn'),                        // 2 显式契约
  (p) => p.locator('form[data-form="order"] button[type=submit]'), // 3 锚点+属性
  (p) => p.getByText('提交', { exact: true }),               // 4 文案兜底
];

async function resolve(page, candidates, { timeout = 8000 } = {}) {
  const perTry = Math.floor(timeout / candidates.length);
  for (const [i, build] of candidates.entries()) {
    const loc = build(page);
    try {
      await loc.waitFor({ state: 'visible', timeout: perTry });
      if (await loc.count() === 1) return { loc, tier: i + 1 };   // 唯一命中才算安全
    } catch { /* 换下一档 */ }
  }
  throw new Error('所有定位档位均失败，需人工介入并更新定位契约');
}

const { loc, tier } = await resolve(page, CANDIDATES);
console.log('命中档位：', tier);           // 档位数字变大 = 页面在漂，写进指标
await loc.click();
await page.waitForURL(/\/orders\/\d+/, { timeout: 15000 });  // 用语义信号确认，不用 sleep
```

关键点三条：候选档位**按稳定性降序**排列；每档只给总预算的 `1/N`；**命中唯一元素**才允许动作（命中 0 个或多个都算失败）。完整档位表与降级策略见 `references/locator-and-wait.md`。

### 路径三：Agent 循环（模型自己看页面、自己决定点哪里）

人写死选择器适合固定流程；让模型驱动适合页面会变、流程会分叉的场景。稳定的做法不是把整页 HTML 丢给模型，而是先把页面压成**语义快照**：

```javascript
// 每个交互元素给一个短编号，模型只回编号，不回选择器
async function snapshot(page) {
  const nodes = await page.locator('a, button, input, select, textarea, [role]').all();
  const items = [];
  for (const [i, n] of nodes.entries()) {
    if (!(await n.isVisible())) continue;                 // 不可见的不要给模型，省 token 也少误点
    items.push({
      id: i,
      role: (await n.getAttribute('role')) ?? await n.evaluate(e => e.tagName.toLowerCase()),
      name: ((await n.innerText().catch(() => '')) || '').trim().slice(0, 60),
      disabled: await n.isDisabled().catch(() => false),
    });
    if (items.length >= 80) break;                        // 截断，防止上下文爆炸
  }
  return { url: page.url(), title: await page.title(), elements: items };
}

const snap = await snapshot(page);
// → 交给模型：[{id:12, role:'button', name:'提交订单', disabled:false}, ...]
// ← 模型返回：{"action":"click","id":12,"reason":"提交当前订单"}
// 你再用编号回填到真实元素，动作前后各留一张截图
```

三条纪律：**编号每轮重算**（DOM 变了编号就作废，不要把上轮的 id 用到下一轮）；**动作前重取快照**；**一次只做一个动作**，做完立刻校验页面状态。多模态模型看图定位同样可行，但要把截图坐标与元素边界对齐（`boundingBox()`），并接受「模型报的坐标点偏」这类误差——细节见 `references/core-concepts.md`。

### 路径四：登录态复用、截图与下载

```bash
# 1) 登录一次，把状态存起来（人工/半自动完成登录那一步）
#    storageState 内含 Cookie，等价于账号凭证 → 立刻加进 .gitignore
mkdir -p .auth && echo ".auth/" >> .gitignore
```

```javascript
// 2) 后续所有任务复用登录态，不再重复登录
const context = await browser.newContext({ storageState: '.auth/user.json' });

// 3) 定期校验登录态是否还有效，失效就报警而不是硬闯
await page.goto('https://example.com/dashboard');
if (page.url().includes('/login')) throw new Error('登录态已过期，需要重新授权');

// 4) 下载：先挂等待，再触发，最后另存（顺序反了必然丢文件）
const downloading = page.waitForEvent('download', { timeout: 60000 });
await page.getByRole('button', { name: '导出对账单' }).click();
const file = await downloading;
await file.saveAs(`out/${file.suggestedFilename()}`);   // 上下文一关，临时文件就没了
```

截图与取值的三条分工规则：**要给人看 / 给多模态模型看 → 截图**；**要结构化字段 / 要喂文本模型 → DOM 取值**；**要复现失败现场 → 两者都留，外加 trace**。别用截图当数据源去做数值比较，分辨率与缩放会骗你。

## 工作流路由

| 用户要什么 | 看哪份 |
|---|---|
| 选型：Playwright / Puppeteer / Selenium / 纯 CDP / Agent 框架，各自适合什么场景 | `references/core-concepts.md` |
| 搞清会话、上下文、页面、框架、标签页之间的关系与生命周期 | `references/core-concepts.md` |
| 元素定位怎么写才不容易失效、失效后按什么顺序降级 | `references/locator-and-wait.md` |
| 等待策略怎么定：自动等待、断言等待、显式等待、网络等待、禁止硬睡 | `references/locator-and-wait.md` |
| 重试怎么设计：动作级重试与步骤级重规划，退避与预算 | `references/locator-and-wait.md` |
| 截图、DOM 取值、ARIA 快照怎么分工，怎么做可观测性 | `references/core-concepts.md` |
| 登录态（storageState / 用户数据目录）怎么存、怎么复用、怎么过期处理 | `references/safety-and-troubleshooting.md` |
| 验证码、反爬、频控、robots 的边界在哪，授权怎么确认 | `references/safety-and-troubleshooting.md` |
| 报错排查：超时、元素找不到、点击被遮挡、iframe、弹窗、下载失败 | `references/safety-and-troubleshooting.md` |

## 能力边界

**覆盖**：

- **会话编排**：浏览器进程 → 上下文 → 页面 → 框架的四层模型与生命周期；一个上下文一个身份（Cookie / 本地存储 / 权限隔离），多账号任务隔离，标签页与弹窗的接管与归还。
- **元素定位**：语义优先的定位器梯度（角色 + 可访问名 → 标签 / 占位符 / 文案 → 显式测试契约 → 稳定属性锚点），唯一性校验，作用域收窄，iframe 与 Shadow DOM 处理，候选档位 + 降级链写法。
- **等待策略**：动作前的自动等待与可操作性检查（可见、稳定、可接收事件、可用、可编辑）、断言级等待、显式状态等待、网络与导航等待，以及每类等待的超时预算分配。
- **交互动作**：点击 / 双击 / 右键 / 悬停 / 拖拽、输入与逐字键入、下拉选择、勾选、键盘组合键、滚动、文件上传。
- **取值与产物**：DOM 文本 / 属性 / 表格 / 列表结构化提取，ARIA 语义快照压缩给模型，全页与元素级截图，视频录制，trace 留痕，控制台与网络日志。
- **下载与文件**：下载事件监听、另存与重命名、临时目录语义、上传路径设置。
- **登录态**：登录一次存档、后续复用、有效性探测、失效识别与重新授权流程。
- **稳定性工程**：候选档位与命中率指标、动作级重试与步骤级重规划、幂等与断点续跑、失败现场三件套（截图 + 快照 + 日志）。
- **合规与安全**：授权站点确认清单、robots 与条款边界、限速与并发上限、敏感字段脱敏、登录态文件的存储纪律。

**不覆盖**：

- **不提供任何验证码 / 人机校验的绕过手段**。图形验证码、滑块、点选、短信验证码一律不做自动识别与破解；正确路径是站点官方接口、申请测试账号、人工介入，或直接放弃该步骤。
- **不做反检测对抗**。不涉及指纹伪装、浏览器特征篡改、代理池轮换规避风控、行为轨迹伪造。这些既越界也不稳定。
- **不做风控与频控的规避**。不通过切换 IP / 账号 / UA 来绕开站点限流。触发限流就退避、降速、缩量，或改走官方数据接口。
- **不含破解登录**。不提供撞库、口令爆破、越权访问他人账号的任何方法。
- **不做业务侧加工**。数据清洗、去重、入库、向量化、报表生成属于下游环节。
- **不做大规模爬取架构**。代理池、分布式调度、反爬对抗不在范围内；那是采集引擎的领域，浏览器自动化负责「像人一样把该点的点掉」。
- **不覆盖移动端原生 App**。只做浏览器环境；原生 App 自动化是另一套体系。
- **不发布、不托管任何第三方源码**。正文为原创整理，只引用公开 API 的方法名、选项名与行为定义等事实性信息。

## 依赖条件

- **运行时**：Node.js 18+（Playwright / Puppeteer 路线）或 Python 3.9+（Playwright Python 路线）；Selenium 路线另需对应语言的驱动管理。
- **浏览器内核**：至少装一个内核（推荐 Chromium）。首装会下载上百 MB，内网环境需先配好镜像或离线包目录；容器里跑要额外装系统依赖。
- **系统依赖**：Linux 无桌面环境需 `--with-deps` 一类系统库安装步骤；Windows / macOS 通常开箱可用。无头模式默认开启，截图与 PDF 在无头下同样可用。
- **权限**：以当前用户身份拉起浏览器进程，需要可执行的临时目录；下载目录、截图目录、登录态目录需要写权限。
- **网络**：能访问目标站点；如目标站在内网，需保证运行环境可达。走代理时要显式配置，别依赖系统环境变量的隐式生效。
- **磁盘**：截图、视频、trace 会迅速吃掉空间；视频与 trace 建议只在调试期开启，并对产物目录定期清理。
- **凭证**：涉及登录的任务需要账号与密码来源（环境变量 / 密钥管理），以及一个可写的登录态存档路径。

## 已知限制

- **选择器失效不是运气问题，是必然事件**。前端改版、A/B 实验、文案微调、组件库升级都会打断定位。把「定位契约」当成需要维护的资产，并给每档候选打命中率指标。
- **自动等待不是万能药**。它只处理「元素何时可交互」，不理解业务语义——按钮可点了不代表后端已经处理完。业务完成信号必须自己定义（URL 变化、列表新增一行、toast 出现、接口返回 200）。
- **`networkidle` 不适合做通用等待条件**。长轮询、埋点上报、心跳请求会让它永远不空闲，或者在你以为空闲时又冒出新请求；只在明确知道页面请求会停的场景用它。
- **无头与有头行为存在差异**。部分站点对无头环境返回不同内容或更严的风控；遇到「有头能跑、无头不行」，先怀疑这一条，而不是继续加重试。
- **截图不等于真相**。动画未结束、懒加载未触发、字体未就绪都会截到假象；关键截图前先等元素稳定（连续两帧边界框不变）。
- **下载是异步事件，不是返回值**。先 `waitForEvent` 再触发，顺序反了就是随机丢文件；且文件在上下文关闭时被清理，必须及时 `saveAs`。
- **iframe 与 Shadow DOM 会吃掉定位**。主文档里找不到的元素，先确认它在哪一层；跨域 iframe 的能力受同源策略限制。
- **验证码是硬边界**。任何声称「自动过验证码」的方案，要么违反站点条款，要么极不稳定，本规范一律不提供。
- **登录态会过期**。Cookie 有 TTL、会话可能被踢、Token 可能轮换；把它当会失效的缓存，而不是长期凭证。
- **模型驱动循环的成本不可忽略**。每轮快照 + 推理都有 token 与延迟开销，长流程会放大；对固定流程优先用确定性脚本，只在不确定性高的环节引入模型。
- **并发不是免费加速**。同一账号并发会互相踢下线、共享状态互相污染；并发之前先确认账号与数据是否允许并行。

## 自检清单

- [ ] 目标站点已获授权，或本就是自有 / 客户授权的系统；已确认 robots 与站点条款没有禁止这类访问。
- [ ] 账号密码走环境变量或密钥管理，代码、配置、日志里搜不到明文。
- [ ] `.auth/`、下载目录、截图目录都已加入忽略规则，不会随提交外发。
- [ ] 每个交互元素都用「角色 + 可访问名」起手，没有裸 `nth-child` / 自动生成的 class / 绝对 XPath。
- [ ] 每个定位候选都校验**唯一命中**（`count() === 1`）才执行动作。
- [ ] 每档候选都设了独立超时，总预算有上限，超时后不是无限重试而是明确失败。
- [ ] 等待用的是语义信号（URL / 元素状态 / 业务标记），全篇没有 `waitForTimeout(5000)` 这种硬睡（除调试期）。
- [ ] 有降级链：主定位失效时依次尝试候选档位，全部失败则带截图与快照报错退出。
- [ ] 关键动作前后各有一张截图或一条结构化日志，失败时能还原现场。
- [ ] 下载流程是「先挂监听、再触发、后 `saveAs`」，并处理了超时与空文件。
- [ ] 登录态有有效性探测；失效时抛错并提示重新授权，而不是继续在登录页上乱点。
- [ ] 遇到验证码 / 限流 / 403 时脚本**停下来并上报**，没有实现任何绕过或伪装逻辑。
- [ ] 批量任务有限速与并发上限，且失败项与成功项分开记录，支持单独重跑。
- [ ] 长任务在后台运行并保证浏览器进程会被释放（`finally` 里 `close`），不会堆积僵尸进程。
- [ ] 视频与 trace 只在调试期开启，产物目录有清理策略。

## 参考文件

| 文件 | 用途 |
|---|---|
| `references/core-concepts.md` | 核心模型与选型：浏览器/上下文/页面/框架四层结构、定位器与等待的底层语义、截图 / DOM / ARIA 快照三种取值通道的分工、主流方案（Playwright / Puppeteer / Selenium / 纯 CDP / Agent 驱动）的差异与适用场景 |
| `references/locator-and-wait.md` | 定位与等待的稳定性写法：定位器优先级梯度与反模式、候选档位 + 降级链模板、五类等待的适用边界与超时预算、动作级重试与步骤级重规划的退避参数、命中率指标与回归自测 |
| `references/safety-and-troubleshooting.md` | 安全边界与排错：授权确认清单、robots 与条款、限速与并发纪律、登录态存储与过期处理、验证码 / 反爬 / 风控的正确应对（明确不做绕过）、脱敏与日志纪律，以及超时、找不到元素、点击被遮挡、iframe、弹窗、下载失败、内存与僵尸进程的逐条排查 |

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
