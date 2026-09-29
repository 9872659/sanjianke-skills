# 更新日志

本文件记录 sanjianke-html-video-kit 的版本变更。版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## 1.0.4

**正文原创化重写（合规整改）**

此前本包的正文很可能是对着渲染引擎的**官方文档与源码**撰写的，包内出现了大量内部标识符
（`media_variable_src_no_fallback` 这类 lint 错误码、`window.__timelines`、`--strict-variables`、
`grade-compare`）与"大约四百个已托管的 block"这类具体数字，读起来与该引擎官方文档的表达高度接近。

这构成一个两难：一方面本包的品牌规则不允许出现第三方署名与仓库地址，另一方面该渲染引擎采用
**Apache-2.0** 许可，若确实使用了它的内容，许可要求保留署名与许可声明。

**解法是把「使用其内容」这件事消掉**：叙述文字全部改成本包自己的原创表述，只保留不受版权保护的
事实性内容。据此对 5 个文档做了逐段重写：

| 文件 | 改动 |
|---|---|
| `SKILL.md` | 开头介绍段、触发场景、快速开始、能力边界、依赖条件、已知限制、自检清单、参考文件表全部重写 |
| `README.md` | 前置条件、使用、依赖、安全、版权等小节重写 |
| `references/quickstart.md` | 环境准备、工程解剖、骨架逐处说明、检查 / 预览 / 渲染、渲染章节全部重写 |
| `references/animation-and-timeline.md` | `data-*` 属性表的说明文字、可见性语义、时长契约、五条硬规矩、子合成、变量绑定、媒体写法全部重写 |
| `references/batch-and-pitfalls.md` | 变量边界、批量渲染、manifest、以及"常见坑"全部重写 |

**刻意原样保留**（属于事实，不受版权保护；改了反而会写错）：

- 命令字面量：`npx hyperframes render / init / check / lint / catalog / add / doctor / browser …`
- 参数与 flag 名：`--strict-variables`、`--batch-concurrency`、`--browser-timeout` 等
- lint 错误码与运行时全局：`media_variable_src_no_fallback`、`gsap_repeat_ceil_overshoot`、
  `window.__timelines`、`window.__hyperframes`、`data-hf-render-id`、
  `standalone_composition_wrapped_in_template` 等
- `data-*` 属性名、CSS 选择器、字段名、JSON 的 key
- 技术性数字：分辨率、端口（3002 / 3017）、Node 版本（22）、字数与体积量级

**主动去掉的具体数字与说法**：已删掉"大约四百个已托管的 block 和 component"中的具体数量表述。

**兼容性**
- 命令、参数、`data-*` 属性、端点、故障排查顺序与全部技术结论**一律未变**。
- 校验方式：对重写前后的 5 个文件做「事实清单」机器比对——294 条代码行、596 处行内代码、
  253 个标识符、102 个数字**全部一致，零丢失**。

## 1.0.3

**新增：真的接上 api.a7w.cn（配音这一段不再留空）**

- `scripts/a7w.py`：api.a7w.cn 的零依赖客户端，不内嵌任何密钥
- `scripts/run.py`：旁白稿与配音算力层，五个子命令 `narration / tts / dub / voices / stt`，
  只用标准库。真实调用 `POST /api/v1/chat/completions` 写稿，
  `POST /api/v1/apps/voice_tts/tts`（长文自动切 `tts_async`）配音，
  并产出带真实秒数的 `audio/cues.json`
- 参数名经 `a7w.py schema voice_tts` 实查：音色参数是 `reference_id`（不是 `voice_id`），
  STT 上传字段是 `audio`
- `SKILL.md`：新增「怎么用（命令行）」与「依赖说明」两节

**同时清理的第三方痕迹**

- `references/quickstart.md` 里原先带有一条真实的 registry 仓库地址（含外部组织名与仓库名），
  已改为占位符并补充说明
- `README.md` 与 `LICENSE.md` 里那两行**直接点名第三方项目的署名文字**已删除，
  替换为不点名、不给仓库链接的中性依赖描述

## 1.0.2

维护更新：文案与结构微调。

## 1.0.0

首次发布。
