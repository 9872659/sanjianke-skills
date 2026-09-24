# 角色与课堂流程配置

适用：想搞清「AI 教师和智能体同学到底怎么分工」、怎么加角色、课堂按什么顺序推进、卡在哪一步该看什么。

## 1. 角色模型：一个角色就是一条配置

每个智能体都是同一套结构，关键字段如下（字段名以代码里的类型定义为准）：

| 字段 | 作用 | 取值要点 |
|---|---|---|
| `id` | 唯一标识 | 系统分配，生成的角色还会带 `boundStageId` |
| `name` | 显示名 | 建议 2～5 个汉字，出现在头像条与对话里 |
| `role` | 角色档位 | 决定行动权限，见第 2 节 |
| `persona` | 人设正文 | 实际塞进系统提示的那段，写得越具体越不容易「串味」 |
| `avatar` | 头像 | emoji 或图片路径，默认头像表里有 10 个可选 |
| `color` | 主题色 | 12 色调色板循环分配，用于区分说话人 |
| `allowedActions` | 允许的动作 | 不填时按 `role` 自动推导 |
| `priority` | 导演选人优先级 | 1～10，数值越大越容易被点名 |
| `voiceConfig` | 该角色的音色 | `providerId` + `modelId` + `voiceId` 三件套，可逐角色指定 |
| `voiceDesign` | 音色描述 | 三层声线描述，用于「自动音色」模式，不依赖具体服务商 |
| `isDefault` | 是否模板 | 默认真值用于内置模板角色 |
| `isGenerated` | 是否 AI 生成 | 由模型按课程内容临时生成的角色为 true |

调角色时最常被忽略的是 `priority` 和 `persona` 的搭配：`priority` 只决定「谁先开口」，`persona` 才决定「开口说什么」。想让课堂有辩论感，就把两个角色的 `priority` 拉开、`persona` 写成对立立场，而不是把两个人都写成「乐于助人的同学」。

## 2. 角色 → 行动权限

代码里只区分三档，未知 `role` 一律降级为「只有白板权限」：

| 角色 | 可用动作 |
|---|---|
| `teacher` | 幻灯片动作（`spotlight` 聚光、`laser` 激光笔、`play_video` 播视频）**加上**全部白板动作 |
| `assistant` | 仅白板动作 |
| `student` | 仅白板动作 |

白板动作共 12 种：`wb_open`、`wb_close`、`wb_draw_text`、`wb_draw_shape`、`wb_draw_chart`、`wb_draw_latex`、`wb_draw_table`、`wb_draw_line`、`wb_draw_code`、`wb_edit_code`、`wb_clear`、`wb_delete`。

推论：

- **只有 `teacher` 能控制幻灯片**。想让某个角色能翻页、打聚光灯，就把它的 `role` 设为 `teacher`，而不是手动往 `allowedActions` 里堆动作——手动填容易被后续推导逻辑覆盖。
- 想让「同学」上讲台写公式，保留 `student` 即可，白板动作本来就够；想让它翻页就不行。
- 角色名册可以由模型生成：`POST /api/generate/agent-profiles`。生成出来的角色颜色与头像从固定调色板和头像表里循环取，所以同一节课里角色不会撞脸。

## 3. 课堂内容：四种场景

一节课堂由若干**场景**按顺序串成，每条大纲对应一个场景，类型四选一：

| 场景 | 白板/交互表现 | 什么时候用 |
|---|---|---|
| 幻灯片 | 教师语音讲解 + 聚光灯/激光笔引导，元素可含图片、图表、LaTeX | 概念铺陈、结论讲解 |
| 测验 | 单选 / 多选 / 简答，AI 实时判分给反馈 | 每个知识点的收口检查 |
| 交互 | 一段自包含 HTML，可动手拖拽调节 | 需要「看见变化」的原理类内容 |
| 项目制学习 | 选角色与智能体协作走里程碑、交交付物 | 综合实战、长任务 |

「深度交互模式」是交互场景的加强档，交互界面具体形态有五种：3D 可视化、模拟实验、知识小游戏、思维导图、在线编程。教师角色可以主动操作这些界面（高亮区域、设定条件、给提示），并且全部响应式适配桌面 / 平板 / 手机。

选场景的经验规则：

- 纯记忆型内容 → 幻灯片 + 测验，别硬塞交互。
- 有「参数变了结果就变」的内容（物理模拟、算法可视化、财务模型）→ 值得上交互。
- 需要产出物（报告、方案、代码）→ 用项目制学习，里程碑设计要写进大纲里。

## 4. 两阶段生成流水线

生成是**两段式**，不要指望一次调用出成品：

```
输入（一句话需求 / PDF 内容 / 素材）
   ↓  阶段一：大纲生成
结构化大纲（每个条目 → 一个场景的类型与主题）
   ↓  阶段二：场景内容生成（可并发）
每个场景的具体内容：幻灯片元素 / 题目 / HTML / 项目结构
   ↓
可播放的课堂
```

命令行提交与轮询：

```bash
# 提交（异步，返回 202）
curl -s -X POST http://localhost:3000/api/generate-classroom \
  -H 'Content-Type: application/json' \
  -d '{"requirement":"零基础 30 分钟看懂线性回归","agentMode":true}'

# 轮询（建议 5 秒一次，跟返回里的 pollIntervalMs 保持一致）
curl -s http://localhost:3000/api/generate-classroom/<jobId>
```

请求体里可控的开关（都是可选，不传走默认）：

| 字段 | 说明 |
|---|---|
| `requirement` | 必填，主题或需求描述 |
| `pdfContent` | 已解析的文档正文，用于「基于材料生成」 |
| `agentMode` | 是否启用多智能体课堂模式 |
| `enableWebSearch` / `webSearchProviderId` / `webSearchModelId` | 是否让智能体在课堂里联网检索 |
| `enableImageGeneration` / `enableVideoGeneration` | 是否允许出图 / 出视频 |
| `enableTTS` | 是否合成语音讲解 |

分步调试时可以直接打底层端点，比反复跑整条流水线快得多：

- `/api/generate/scene-outlines-stream` —— 流式出大纲，先看结构对不对
- `/api/generate/scene-content` —— 单场景内容
- `/api/generate/scene-actions` —— 单场景动作序列
- `/api/generate/agent-profiles` —— 角色名册
- `/api/generate/image`、`/api/generate/video`、`/api/generate/tts`、`/api/generate/voice` —— 媒体与语音

**排查心法：先看大纲，再看单场景，最后才看整条链路。**大纲错了，后面全错。

## 5. 回放状态机：课堂怎么「动」起来

播放引擎是个四态机：

```
idle ──开始──▶ playing ──暂停──▶ paused ──继续──▶ playing
                  │                                  │
                  └──────── 用户插话 / 触发讨论 ──▶ live ──▶ playing
```

| 状态 | 含义 | 用户可以做什么 |
|---|---|---|
| `idle` | 未开始，停在第一个场景 | 挑选参与讨论的智能体、调语速 |
| `playing` | 按动作序列推进：说话 → 白板绘制 → 特效 → 下一动作 | 暂停、打断提问 |
| `paused` | 停在当前动作 | 继续、跳到指定动作 |
| `live` | 实时讨论中，智能体之间以及和你之间自由发言 | 随时插话、结束讨论回到 `playing` |

关键回调（做二次开发或接播放器时用得上）：

- 说话：`onSpeechStart` / `onSpeechEnd` / `onTextDelta` / `onSpeakerChange`（流式增量走 `onTextDelta`）
- 画面：`onSceneChange` / `onEffectFire`（特效只有两种：聚光 `spotlight`、激光 `laser`）
- 讨论：`onProactiveShow`（主动弹出讨论卡片，带 `question` 与推荐发言人）/ `onDiscussionConfirmed` / `onDiscussionEnd` / `onUserInterrupt`
- 进度：`onProgress` 吐出快照 `{ sceneIndex, actionIndex, consumedDiscussions, sceneId }`，持久化就是存这个
- 语速倍率支持 1 / 1.5 / 2 三档

讨论话题本身也有三态：`pending`（已排队）→ `active`（正在进行）→ `closed`（已收束）。已经消费过的话题会记在 `consumedDiscussions` 里，避免重放时再弹一遍。

## 6. 编排层在做什么

多智能体不是「把所有角色都叫一遍」，中间有个导演层在调度：

1. **选人**：按 `priority`、话题相关性和每个角色的 `allowedActions` 挑出本轮发言者。
2. **给上下文**：把当前场景状态、白板已达成的结论、其他角色的近期发言摘要，压成短上下文再喂给发言者。
3. **防打架**：白板是共享资源，多个角色同时画会冲突，所以有白板账本与冲突消解——同一个位置谁先落笔谁算数。
4. **控长度**：代码类输出有行数预算，超了会被截断，避免一个角色把上下文吃光。
5. **收尾**：讨论结束回到播放态，把结论并入后续场景的上下文。

所以「某个同学一直不说话」通常不是它坏了，而是 `priority` 太低或话题相关性不足，没被选上。

## 7. 加一个新角色（最小步骤）

1. 想清楚它的 `role`：要控幻灯片就是 `teacher`，否则 `assistant` 或 `student`。
2. 写 `persona`：一行身份 + 一行关注点 + 一行说话习惯。参考句式「你是 X，关注 Y，说话 Z」。
3. 定 `priority`：主讲 8～10，主力同学 5～7，偶尔插话的 1～3。
4. 选 `color` 与 `avatar`：从默认 12 色与 10 个头像里挑没被占的，避免视觉混淆。
5. 定音色：指定 `voiceConfig`，或用 `voiceDesign` 走自动音色，后者不绑定具体服务商。
6. 跑一节 3～5 分钟的小课验证：它有没有在合适的时机开口、有没有做出符合权限的动作。
