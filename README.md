# 三剪客 Skills

给 AI Agent 用的一组技能包（Skill），遵循 **SKILL.md** 约定，
可直接被 Claude / OpenAI / Coze / SkillHub / ClawHub 等支持 SKILL.md 的平台加载。

**320 个技能包**：93 个三剪客原创，228 个为第三方开源项目编写的原创使用指南。

## 目录结构

```
sanjianke-skills/
├── skills/
│   └── <skill-slug>/
│       ├── SKILL.md        # 技能主入口（frontmatter + 正文）
│       ├── README.md       # 人读的说明
│       ├── LICENSE.md      # 许可；衍生包在此署名上游项目
│       ├── references/     # 细节文档（可选）
│       └── scripts/        # 可执行脚本（可选）
├── index.json              # 机器可读的技能清单
├── THIRD-PARTY.md          # 第三方项目与署名
└── LICENSE
```

## 怎么用

**方式一：手动复制** —— 把 `skills/<slug>/` 整个目录放进你的 Agent 技能目录即可。

**方式二：命令行安装**（ClawHub）

```bash
npx clawhub install <slug>
```

**方式三：让 Agent 自己读** —— 把 `SKILL.md` 的路径或内容直接交给 Agent。

## 关于正文里出现的路径

衍生指南的正文里会出现 `docs/xxx.md`、`configs/xxx.yaml`、`scripts/xxx.py` 这类路径。
**这些是被介绍的上游项目仓库里的文件，不在本仓库内。**
需要时先按该 Skill 的安装说明克隆上游仓库，再进仓库根目录按对应路径找。

本仓库自带的脚本，只有各 Skill 目录自己的 `scripts/` 子目录
（通常是一两个零依赖客户端，例如 `scripts/run.py`、`scripts/a7w.py`）。
正文里凡是指向本包文件的引用，都会写成 `references/…` 或本包 `scripts/…` 并能对上号。

## 技能分类

### 内容创作（40）

- **`sanjianke-ai-workflow`** 可视化AI工作流编排·OpenAI兼容网关接21个生成应用
- **`sanjianke-article-shape-kit`** 三剪客 · 文章结构设计
- **`sanjianke-bg-remover`** 图片一键去背景换白底·商品图抠图透明底批量在线工具
- **`sanjianke-canvas-drama`** AI短剧创作画布·智能分镜图像视频生成一站式出片工作流
- **`sanjianke-coqui-tts`** 三剪客 · 开源语音合成与音色克隆 · 衍生指南
- **`sanjianke-doc-to-markdown`** 文档转Markdown·PDF Word表格结构保留在线工具
- **`sanjianke-drama-factory`** AI短剧量产工厂·小说改编剧本分镜图视频配音全流程一键出片
- **`sanjianke-drama-workbench`** AI短剧制作工作台·多应用组合配方单镜头SOP与批量排产
- **`sanjianke-faster-whisper`** 三剪客 · 语音转文字与字幕生成 · 衍生指南
- **`sanjianke-ffmpeg-python`** 三剪客 · FFmpeg 的 Python 绑定 · 衍生指南
- **`sanjianke-ffsubsync`** 三剪客 · 字幕与视频自动对齐 · 衍生指南
- **`sanjianke-funasr`** 三剪客 · 语音识别与说话人分离工具箱 · 衍生指南
- **`sanjianke-funclip`** 三剪客 · 识别文字自动剪视频 · 衍生指南
- **`sanjianke-graph-rag`** 图谱增强检索知识库·实体关系抽取社区摘要全局趋势问答一条龙
- **`sanjianke-image-to-text`** 图片文档一键转文字·截图海报表格文字提取在线OCR工具
- **`sanjianke-insanely-fast-whisper`** 三剪客 · 极速语音转写 · 衍生指南
- **`sanjianke-light-rag`** 轻量图谱知识库搭建·实体关系抽取双层级检索跨文档问答零部署
- **`sanjianke-llm-flow-builder`** 拖拽式LLM流程编排·画布搭Agent接OpenAI兼容模型网关
- **`sanjianke-moviepy`** 三剪客 · Python 视频剪辑库 · 衍生指南
- **`sanjianke-paddlespeech`** 三剪客 · 语音识别与合成工具箱 · 衍生指南
- **`sanjianke-pyannote-audio`** 三剪客 · 说话人分离与日志化 · 衍生指南
- **`sanjianke-pydub`** 三剪客 · 音频切片与格式转换 · 衍生指南
- **`sanjianke-rag-pipeline`** RAG知识库流水线搭建·文档切分向量检索大模型问答一条龙零部署
- **`sanjianke-remotion`** 三剪客 · 用 React 写代码生成视频 · 衍生指南
- **`sanjianke-sensevoice`** 三剪客 · 多语言语音理解（识别 / 语种 / 情感 / 事件） · 衍生指南
- **`sanjianke-short-video-maker`** AI短视频一键生成·选题脚本配音画面字幕全流程批量出片
- **`sanjianke-shortgpt`** 三剪客 · AI 短视频自动化生产框架 · 衍生指南
- **`sanjianke-spleeter`** 三剪客 · 人声伴奏分离 · 衍生指南
- **`sanjianke-stem-split`** 歌曲伴奏人声分离·一键提取鼓点贝斯四轨拆解在线工具
- **`sanjianke-subtitle-edit`** 三剪客 · 字幕编辑与时间轴校对工具 · 衍生指南
- **`sanjianke-subtitle-maker`** 音视频一键转字幕·语音转文字自动生成SRT时间轴批量出稿
- **`sanjianke-vector-store`** 轻量向量库检索搭建·文档向量化语义搜索元数据过滤知识库零显卡
- **`sanjianke-video-subtitle-extractor`** 三剪客 · 视频硬字幕提取成 SRT · 衍生指南
- **`sanjianke-video2x`** 三剪客 · 视频超分与补帧 · 衍生指南
- **`sanjianke-whisper`** 三剪客 · 语音识别与转写 · 衍生指南
- **`sanjianke-whisper-cpp`** 三剪客 · 本地语音转文字与字幕 · 衍生指南
- **`sanjianke-whisper-diarization`** 三剪客 · 说话人分离转写 · 衍生指南
- **`sanjianke-whisperx`** 三剪客 · 音视频转写与逐词对轴 · 衍生指南
- **`sanjianke-youtube-transcript-api`** 三剪客 · YouTube 字幕与转写抓取 · 衍生指南
- **`sanjianke-yt-dlp`** 三剪客 · 全网视频音频下载器 · 衍生指南

### 设计多媒体（38）

- **`a7w-action-transfer`** 三剪客 · 动作迁移
- **`a7w-dressing-diffusion`** 三剪客 · AI换装
- **`a7w-flashvsr`** 三剪客 · 视频超分（糊片救 4K）
- **`a7w-full-video`** 三剪客 · 全能视频生成
- **`a7w-grok-video`** 三剪客 · Grok 视频生成
- **`a7w-happy-horse`** 三剪客 · Happy Horse
- **`a7w-image-human`** AI数字人视频生成照片说话口播虚拟主播带货视频一键出片2K4K高清
- **`a7w-lipsync`** 三剪客 · 数字人对口型
- **`a7w-mmaudio`** 三剪客 · 音效生成、视频配音
- **`a7w-music-generation`** 三剪客 · 音乐生成
- **`a7w-nano-banana`** 三剪客 · nano-banana
- **`a7w-person-replacement`** 三剪客 · 人物替换
- **`a7w-seedance`** 三剪客 · Seedance 2.0
- **`a7w-seedsvc`** 三剪客 · 音色修改、AI翻唱
- **`a7w-smart-clip`** 三剪客 · 智能剪辑
- **`a7w-voice-tts`** 三剪客 · 语音TTS
- **`a7w-wan`** 三剪客 · Wan 视频生成
- **`action-transfer`** 三剪客 · 动作迁移
- **`ai-music-studio`** AI音乐生成歌曲写词作曲编曲演唱人声克隆翻唱伴奏分轨混音一键出歌
- **`dressing-diffusion`** 三剪客 · AI换装
- **`flashvsr`** 三剪客 · 视频超分
- **`full-video`** 三剪客 · 全能视频生成
- **`grok-video`** 三剪客 · Grok 视频生成
- **`happy-horse-video`** 三剪客 · Happy Horse
- **`image-human`** AI数字人视频生成照片说话口播虚拟主播带货视频一键出片2K4K高清
- **`lipsync`** 三剪客 · 数字人对口型
- **`mmaudio`** 三剪客 · 音效生成、视频配音
- **`music-generation-kit`** 三剪客 · 音乐生成
- **`nano-banana-image`** 三剪客 · nano-banana
- **`person-replacement`** 三剪客 · 人物替换
- **`sanjianke-code-video-kit`** 三剪客 · 代码化视频生成 · 衍生指南
- **`sanjianke-html-video-kit`** 三剪客 · HTML 转视频引擎
- **`sanjianke-video-upscale`** 三剪客 · 视频超分（糊片救 4K）
- **`seedance-video`** 三剪客 · Seedance 2.0
- **`seedsvc`** 三剪客 · 音色修改、AI翻唱
- **`smart-clip`** 三剪客 · 智能剪辑
- **`voice-tts-studio`** 三剪客 · 语音TTS
- **`wan-video`** 三剪客 · Wan 视频生成

### 办公（33）

- **`sanjianke-affine`** 三剪客 · 知识库与协作白板 · 衍生指南
- **`sanjianke-apitable`** 三剪客 · 开源可视化数据库与多维表格 · 衍生指南
- **`sanjianke-appflowy`** 三剪客 · 开源协作工作空间 · 衍生指南
- **`sanjianke-cal-com`** 三剪客 · 开源预约排期系统 · 衍生指南
- **`sanjianke-chatwoot`** 三剪客 · 自托管多渠道客服工作台 · 衍生指南
- **`sanjianke-cowagent-chatgpt-on-wechat`** 三剪客 · 多平台 IM 机器人接入 · 衍生指南
- **`sanjianke-docmost`** 三剪客 · 团队知识库与文档协作 · 衍生指南
- **`sanjianke-go-cqhttp`** 三剪客 · QQ 机器人协议端 · 衍生指南
- **`sanjianke-halo`** 三剪客 · 自托管内容站点系统 · 衍生指南
- **`sanjianke-jeecgboot`** 三剪客 · 低代码企业级开发平台 · 衍生指南
- **`sanjianke-joplin`** 三剪客 · 开源笔记与知识同步 · 衍生指南
- **`sanjianke-kirara-ai-chatgpt-mirai-qq-bot`** 三剪客 · 多平台 AI 聊天机器人 · 衍生指南
- **`sanjianke-koishi`** 三剪客 · 跨平台聊天机器人框架 · 衍生指南
- **`sanjianke-langbot-qchatgpt`** 三剪客 · 多平台 IM 接大模型的机器人平台 · 衍生指南
- **`sanjianke-leantime`** 三剪客 · 开源项目协作与任务管理台 · 衍生指南
- **`sanjianke-logseq`** 三剪客 · Logseq 大纲双链笔记 · 衍生指南
- **`sanjianke-mattermost`** 三剪客 · 自托管团队协作沟通平台 · 衍生指南
- **`sanjianke-memos`** 三剪客 · 碎片笔记速记 · 衍生指南
- **`sanjianke-mindoc`** 三剪客 · 团队文档管理系统 · 衍生指南
- **`sanjianke-openim`** 三剪客 · 自建 IM 服务端与消息中台 · 衍生指南
- **`sanjianke-outline`** 三剪客 · Outline 团队知识库 · 衍生指南
- **`sanjianke-plane`** 三剪客 · 开源项目管理 · 衍生指南
- **`sanjianke-rocket-chat`** 三剪客 · Rocket.Chat 团队通讯 · 衍生指南
- **`sanjianke-ruoyi-vue-pro`** 三剪客 · 企业级后台管理开发框架 · 衍生指南
- **`sanjianke-siyuan`** 三剪客 · 思源笔记本地知识库 · 衍生指南
- **`sanjianke-teable`** 三剪客 · 多维表格数据库 · 衍生指南
- **`sanjianke-tinode`** 三剪客 · 可自托管的即时通讯服务端 · 衍生指南
- **`sanjianke-trilium-notes`** 三剪客 · 自托管层级知识库笔记 · 衍生指南
- **`sanjianke-vikunja`** 三剪客 · 开源任务与项目管理 · 衍生指南
- **`sanjianke-wechaty`** 三剪客 · 微信聊天机器人框架 · 衍生指南
- **`sanjianke-wiki-js`** 三剪客 · 自托管团队知识库 · 衍生指南
- **`sanjianke-wxjava`** 三剪客 · 微信生态 Java 服务端开发包 · 衍生指南
- **`sanjianke-zulip`** 三剪客 · 话题制团队聊天服务器 · 衍生指南

### 数据分析（24）

- **`sanjianke-ai-research-kit`** 三剪客 · AI 科研全流程
- **`sanjianke-apache-echarts`** 三剪客 · 数据可视化图表库 · 衍生指南
- **`sanjianke-dataease`** 三剪客 · 开源 BI 数据可视化平台 · 衍生指南
- **`sanjianke-doris`** 三剪客 · 实时分析型数据库 · 衍生指南
- **`sanjianke-duckdb`** 三剪客 · 单机分析型 SQL 引擎 · 衍生指南
- **`sanjianke-fg-data-profiling`** 三剪客 · 数据画像与质量体检 · 衍生指南
- **`sanjianke-g2`** 三剪客 · 统计图表可视化语法 · 衍生指南
- **`sanjianke-g6`** 三剪客 · 关系图可视化引擎 · 衍生指南
- **`sanjianke-itchat`** 三剪客 · 个人微信号自动化接口 · 衍生指南
- **`sanjianke-jimureport`** 三剪客 · 在线报表与大屏设计器 · 衍生指南
- **`sanjianke-lightdash`** 三剪客 · BI 即代码分析平台 · 衍生指南
- **`sanjianke-metabase`** 三剪客 · 自助式 BI 与数据看板 · 衍生指南
- **`sanjianke-pandas`** 三剪客 · Python 表格数据分析库 · 衍生指南
- **`sanjianke-plotly-py`** 三剪客 · 交互式数据可视化图表 · 衍生指南
- **`sanjianke-polars`** 三剪客 · 高性能 DataFrame 计算库 · 衍生指南
- **`sanjianke-pyecharts`** 三剪客 · Python 图表生成 · 衍生指南
- **`sanjianke-pygwalker`** 三剪客 · 数据可视化探索 · 衍生指南
- **`sanjianke-seaborn`** 三剪客 · 统计数据可视化 · 衍生指南
- **`sanjianke-sqlalchemy`** 三剪客 · Python SQL 工具包与 ORM · 衍生指南
- **`sanjianke-stock`** 三剪客 · A股量化选股与数据采集 · 衍生指南
- **`sanjianke-streamlit`** 三剪客 · 纯 Python 数据应用框架 · 衍生指南
- **`sanjianke-superset`** 三剪客 · 企业级数据可视化与 BI 平台 · 衍生指南
- **`sanjianke-tushare`** 三剪客 · A股行情与财务数据接口 · 衍生指南
- **`sanjianke-web-scrape-kit`** 三剪客 · 全网数据采集引擎 · 衍生指南

### CLI（22）

- **`sanjianke-asdf`** 三剪客 · 多语言运行时版本管理 · 衍生指南
- **`sanjianke-direnv`** 三剪客 · 目录级环境变量自动加载 · 衍生指南
- **`sanjianke-fastfetch`** 三剪客 · 终端系统信息速览 · 衍生指南
- **`sanjianke-fd`** 三剪客 · 极速文件查找 · 衍生指南
- **`sanjianke-gh-github-cli`** 三剪客 · GitHub 命令行客户端 · 衍生指南
- **`sanjianke-git-extras`** 三剪客 · Git 增强命令集 · 衍生指南
- **`sanjianke-gitleaks`** 三剪客 · gitleaks 密钥扫描 · 衍生指南
- **`sanjianke-gum`** 三剪客 · Shell 脚本交互组件 · 衍生指南
- **`sanjianke-httpie`** 三剪客 · HTTP 命令行客户端 · 衍生指南
- **`sanjianke-hyperfine`** 三剪客 · hyperfine 命令行基准测试 · 衍生指南
- **`sanjianke-k6`** 三剪客 · k6 负载测试 · 衍生指南
- **`sanjianke-lazydocker`** 三剪客 · 终端 Docker 管理面板 · 衍生指南
- **`sanjianke-lsd`** 三剪客 · 现代化 ls 替代品 · 衍生指南
- **`sanjianke-oh-my-posh`** 三剪客 · 跨 Shell 提示符主题引擎 · 衍生指南
- **`sanjianke-powerlevel10k`** 三剪客 · Zsh 极速提示符主题 · 衍生指南
- **`sanjianke-pre-commit`** 三剪客 · Git 提交前钩子管理 · 衍生指南
- **`sanjianke-ruff`** 三剪客 · 极速 Python Linter 与格式化器 · 衍生指南
- **`sanjianke-shellcheck`** 三剪客 · Shell 脚本静态检查 · 衍生指南
- **`sanjianke-starship`** 三剪客 · 跨 Shell 提示符引擎 · 衍生指南
- **`sanjianke-trufflehog`** 三剪客 · trufflehog 密钥与凭证扫描 · 衍生指南
- **`sanjianke-yq`** 三剪客 · YAML 命令行处理 · 衍生指南
- **`sanjianke-zoxide`** 三剪客 · 智能目录跳转 · 衍生指南

### AI（18）

- **`sanjianke-colossalai`** 三剪客 · 大规模并行训练 · 衍生指南
- **`sanjianke-db-gpt`** 三剪客 · 数据库智能问答 · 衍生指南
- **`sanjianke-deepspeed`** 三剪客 · 大模型训练加速 · 衍生指南
- **`sanjianke-langchain-chatchat`** 三剪客 · 本地知识库问答 · 衍生指南
- **`sanjianke-litellm`** 三剪客 · 百模型统一调用 · 衍生指南
- **`sanjianke-llama-cpp`** 三剪客 · 本地 LLM 推理引擎 · 衍生指南
- **`sanjianke-llama-factory`** 三剪客 · 一站式模型微调 · 衍生指南
- **`sanjianke-lmdeploy`** 三剪客 · 模型部署与量化 · 衍生指南
- **`sanjianke-ollama`** 三剪客 · 本地跑大模型 · 衍生指南
- **`sanjianke-one-api`** 三剪客 · 多模型网关聚合 · 衍生指南
- **`sanjianke-open-webui`** 三剪客 · 自托管 AI 对话界面 · 衍生指南
- **`sanjianke-qanything`** 三剪客 · 本地知识库问答 · 衍生指南
- **`sanjianke-qdrant`** 三剪客 · 向量相似度检索 · 衍生指南
- **`sanjianke-qwen`** 三剪客 · 通义千问开源模型 · 衍生指南
- **`sanjianke-sglang`** 三剪客 · 结构化 LLM 推理 · 衍生指南
- **`sanjianke-transformers`** 三剪客 · 模型加载与推理 · 衍生指南
- **`sanjianke-unsloth`** 三剪客 · 低显存微调加速 · 衍生指南
- **`sanjianke-vllm`** 三剪客 · 高吞吐 LLM 推理服务 · 衍生指南

### 开发编程（16）

- **`sanjianke-agent-orchestrator`** 有状态Agent编排·状态图断点续跑与人工审批接统一模型网关
- **`sanjianke-app-backend-kit`** 三剪客 · Postgres 应用后端 · 衍生指南
- **`sanjianke-brainstorm-kit`** 三剪客 · 发散与收敛
- **`sanjianke-direct-output-kit`** 三剪客 · 直给结论输出规范
- **`sanjianke-doc-grill-kit`** 三剪客 · 带资料追问
- **`sanjianke-engineer-skills-kit`** 三剪客 · 工程师技能体系
- **`sanjianke-fullstack-react-kit`** 三剪客 · React 全栈框架
- **`sanjianke-handoff-kit`** 三剪客 · 任务交接文档
- **`sanjianke-idea-grill-kit`** 三剪客 · 想法压力测试
- **`sanjianke-im-server-kit`** 三剪客 · 即时通讯服务端
- **`sanjianke-llm-app-kit`** LLM应用开发套件·统一接口接OpenAI兼容网关换模型只改一行
- **`sanjianke-plan-kit`** 三剪客 · 执行计划拆解
- **`sanjianke-prd-kit`** 三剪客 · 需求文档 PRD
- **`sanjianke-prototype-kit`** 三剪客 · 想法快速原型
- **`sanjianke-ticket-kit`** 三剪客 · 任务票据拆分
- **`sanjianke-vector-db`** 分布式向量数据库检索·亿级向量相似度搜索元数据过滤混合检索

### 电商（16）

- **`sanjianke-aimeos-laravel`** 三剪客 · Laravel 电商套件 · 衍生指南
- **`sanjianke-bagisto`** 三剪客 · 开源跨境电商独立站系统 · 衍生指南
- **`sanjianke-commerce`** 三剪客 · Next.js 电商前端模板 · 衍生指南
- **`sanjianke-dolibarr`** 三剪客 · 企业 ERP 与 CRM · 衍生指南
- **`sanjianke-inventree`** 三剪客 · 开源库存与物料管理系统 · 衍生指南
- **`sanjianke-litemall`** 三剪客 · 小程序商城全栈系统 · 衍生指南
- **`sanjianke-mall-admin-web`** 三剪客 · 电商后台管理前端 · 衍生指南
- **`sanjianke-mall-swarm`** 三剪客 · 微服务电商商城系统 · 衍生指南
- **`sanjianke-mall4cloud`** 三剪客 · 微服务电商中台 · 衍生指南
- **`sanjianke-mall4j`** 三剪客 · Java 商城系统 · 衍生指南
- **`sanjianke-newbee-mall-vue3-app`** 三剪客 · 商城前台 Vue3 源码 · 衍生指南
- **`sanjianke-saleor`** 三剪客 · GraphQL 原生电商后端平台 · 衍生指南
- **`sanjianke-spree`** 三剪客 · 开源无头电商平台 · 衍生指南
- **`sanjianke-sylius`** 三剪客 · 开源电商平台 · 衍生指南
- **`sanjianke-vendure`** 三剪客 · 电商后端框架 · 衍生指南
- **`sanjianke-wechat-app-mall`** 三剪客 · 微信小程序商城前端模板 · 衍生指南

### 中文NLP（16）

- **`sanjianke-bilingual-book-maker`** 三剪客 · 大模型双语电子书翻译 · 衍生指南
- **`sanjianke-chatglm-6b`** 三剪客 · 本地部署的中英双语对话模型 · 衍生指南
- **`sanjianke-chineseocr-lite`** 三剪客 · 超轻量中文 OCR（命令行 + Web 服务） · 衍生指南
- **`sanjianke-emotivoice`** 三剪客 · 多情感多音色语音合成 · 衍生指南
- **`sanjianke-flagembedding`** 三剪客 · BGE 向量检索与重排序工具箱 · 衍生指南
- **`sanjianke-hanlp`** 三剪客 · 多语种自然语言处理 · 衍生指南
- **`sanjianke-immersive-translate`** 三剪客 · 沉浸式双语网页翻译扩展 · 衍生指南
- **`sanjianke-jieba`** 三剪客 · 中文分词与关键词抽取 · 衍生指南
- **`sanjianke-nextai-translator`** 三剪客 · 桌面划词翻译与文本润色 · 衍生指南
- **`sanjianke-paddlenlp`** 三剪客 · 中文 NLP 与 LLM 全流程工具库 · 衍生指南
- **`sanjianke-pot-desktop`** 三剪客 · 跨平台划词翻译与截图 OCR · 衍生指南
- **`sanjianke-pycorrector`** 三剪客 · 中文文本纠错工具箱 · 衍生指南
- **`sanjianke-pyvideotrans`** 三剪客 · 视频翻译与多角色 AI 配音 · 衍生指南
- **`sanjianke-sherpa-onnx`** 三剪客 · 离线语音识别与合成的 ONNX 运行时 · 衍生指南
- **`sanjianke-snownlp`** 三剪客 · 中文文本处理与情感分析 · 衍生指南
- **`sanjianke-wenet`** 三剪客 · 端到端语音识别工具包 · 衍生指南

### AI Agent（14）

- **`sanjianke-agent-app-kit`** 三剪客 · 跨平台 AI Agent 应用 · 衍生指南
- **`sanjianke-agent-control-kit`** 三剪客 · 长任务 Agent 控制平面
- **`sanjianke-agent-crew`** 多角色Agent协作编排·角色分工与流程控制接入指南
- **`sanjianke-agent-memory`** Agent长期记忆库·跨会话用户偏好事实检索接入指南
- **`sanjianke-agent-platform`** 自建本地AI Agent平台·网关常驻多Agent沙箱落地指南
- **`sanjianke-agent-team`** 多智能体软件开发团队·一句话需求生成项目文档与代码骨架
- **`sanjianke-browser-agent-kit`** 三剪客 · 浏览器自动化
- **`sanjianke-browser-operator`** 浏览器自动化操作员·一句话任务让Agent自己点填翻页抓取
- **`sanjianke-cross-app-kit`** 三剪客 · 跨端 App 开发 · 衍生指南
- **`sanjianke-multi-agent-chat`** 多智能体群聊协作·多角色轮流发言与终止条件接入指南
- **`sanjianke-phone-agent-kit`** 三剪客 · 手机自动化控制 · 衍生指南
- **`sanjianke-plan-exec-kit`** 三剪客 · 计划执行与检查点
- **`sanjianke-skill-forge-kit`** 三剪客 · 技能工程
- **`sanjianke-skills-catalog-kit`** 三剪客 · 技能生态实战

### 文档转换（13）

- **`sanjianke-calibre`** 三剪客 · 电子书管理与转换 · 衍生指南
- **`sanjianke-excelize`** 三剪客 · Go 操作 Excel · 衍生指南
- **`sanjianke-marker`** 三剪客 · PDF 转 Markdown · 衍生指南
- **`sanjianke-mineru`** 三剪客 · PDF 高精度转 Markdown · 衍生指南
- **`sanjianke-ocrmypdf`** 三剪客 · 扫描件叠加 OCR 层 · 衍生指南
- **`sanjianke-pandoc`** 三剪客 · 万能格式转换 · 衍生指南
- **`sanjianke-sheetjs`** 三剪客 · 电子表格读写 · 衍生指南
- **`sanjianke-slidev`** 三剪客 · Markdown 写演示文稿 · 衍生指南
- **`sanjianke-stirling-pdf`** 三剪客 · 本地 PDF 工具箱 · 衍生指南
- **`sanjianke-surya`** 三剪客 · 版面分析与表格识别 · 衍生指南
- **`sanjianke-umi-ocr`** 三剪客 · 离线批量 OCR · 衍生指南
- **`sanjianke-unstructured`** 三剪客 · 多格式文档解析 · 衍生指南
- **`sanjianke-wkhtmltopdf`** 三剪客 · HTML 转 PDF · 衍生指南

### 文件管理（12）

- **`sanjianke-dust`** 三剪客 · 磁盘占用可视化的命令行工具 · 衍生指南
- **`sanjianke-ffmpeg`** 三剪客 · 音视频转码与处理 · 衍生指南
- **`sanjianke-filebrowser`** 三剪客 · 网页版文件管理器 · 衍生指南
- **`sanjianke-lf`** 三剪客 · 终端文件管理器 · 衍生指南
- **`sanjianke-lz4`** 三剪客 · 极速无损压缩命令行工具 · 衍生指南
- **`sanjianke-minio`** 三剪客 · 自建 S3 对象存储 · 衍生指南
- **`sanjianke-nextcloud-server`** 三剪客 · 自建网盘与在线协作 · 衍生指南
- **`sanjianke-owncloud-core`** 三剪客 · 自建私有云盘服务端 · 衍生指南
- **`sanjianke-rclone`** 三剪客 · 云存储搬运与同步 · 衍生指南
- **`sanjianke-restic`** 三剪客 · 去重加密备份工具 · 衍生指南
- **`sanjianke-syncthing`** 三剪客 · 跨设备文件持续同步 · 衍生指南
- **`sanjianke-yazi`** 三剪客 · 终端文件管理器 · 衍生指南

### PDF（11）

- **`sanjianke-gotenberg`** 三剪客 · 文档转换 HTTP API · 衍生指南
- **`sanjianke-pdf-extract-kit`** 三剪客 · 文档智能解析工具箱 · 衍生指南
- **`sanjianke-pdf-lib`** 三剪客 · JS 创建修改 PDF · 衍生指南
- **`sanjianke-pdfcpu`** 三剪客 · Go PDF 处理 CLI · 衍生指南
- **`sanjianke-pdfplumber`** 三剪客 · PDF 精细提取 · 衍生指南
- **`sanjianke-pptist`** 三剪客 · 在线 PPT 编辑器 · 衍生指南
- **`sanjianke-pymupdf`** 三剪客 · 高性能 PDF 处理 · 衍生指南
- **`sanjianke-pypdf`** 三剪客 · 纯 Python PDF 操作 · 衍生指南
- **`sanjianke-tabula`** 三剪客 · PDF 表格抽取 · 衍生指南
- **`sanjianke-turndown`** 三剪客 · HTML 转 Markdown · 衍生指南
- **`sanjianke-weasyprint`** 三剪客 · HTML/CSS 转 PDF · 衍生指南

### 文档处理（10）

- **`sanjianke-csvkit`** 三剪客 · CSV 处理 CLI 套件 · 衍生指南
- **`sanjianke-docling`** 三剪客 · 文档转结构化数据 · 衍生指南
- **`sanjianke-mammoth-js`** 三剪客 · docx 转 HTML · 衍生指南
- **`sanjianke-pdf-js`** 三剪客 · PDF 解析与渲染 · 衍生指南
- **`sanjianke-pdfarranger`** 三剪客 · PDF 页面整理 · 衍生指南
- **`sanjianke-pdfminer-six`** 三剪客 · PDF 文本布局解析 · 衍生指南
- **`sanjianke-python-docx`** 三剪客 · 读写 Word 文档 · 衍生指南
- **`sanjianke-qpdf`** 三剪客 · PDF 无损变换 · 衍生指南
- **`sanjianke-tesseract`** 三剪客 · 老牌 OCR 引擎 · 衍生指南
- **`sanjianke-typst`** 三剪客 · 现代排版出 PDF · 衍生指南

### 爬虫（8）

- **`sanjianke-crawlab`** 三剪客 · 分布式爬虫管理平台 · 衍生指南
- **`sanjianke-crawlee-python`** 三剪客 · Python 网页抓取框架 · 衍生指南
- **`sanjianke-easyspider`** 三剪客 · 可视化无代码爬虫 · 衍生指南
- **`sanjianke-matplotlib`** 三剪客 · Python 数据可视化绘图库 · 衍生指南
- **`sanjianke-proxy-pool`** 三剪客 · 免费代理 IP 池服务 · 衍生指南
- **`sanjianke-pyspider`** 三剪客 · 分布式爬虫调度系统 · 衍生指南
- **`sanjianke-scrapegraph-ai`** 三剪客 · 用自然语言驱动网页抓取 · 衍生指南
- **`sanjianke-scrapy`** 三剪客 · Python 网页抓取框架 · 衍生指南

### 社媒（7）

- **`sanjianke-chatgpt-on-wechat`** 三剪客 · 多平台 IM 私域 AI 助理 · 衍生指南
- **`sanjianke-mautic`** 三剪客 · 开源自建营销自动化 · 衍生指南
- **`sanjianke-silenceper-wechat`** 三剪客 · Go 微信 SDK · 衍生指南
- **`sanjianke-tiktokdownload`** 三剪客 · 抖音与 TikTok 作品批量下载 · 衍生指南
- **`sanjianke-wechat-bot`** 三剪客 · 多平台 IM 智能回复机器人 · 衍生指南
- **`sanjianke-wechat-chatgpt`** 三剪客 · 微信接入 ChatGPT 自动回复 · 衍生指南
- **`sanjianke-xiaohongshu-mcp`** 三剪客 · 小红书 MCP 服务 · 衍生指南

### 知识管理（2）

- **`sanjianke-doc-index-qa`** 文档索引与知识检索·数据接进模型接OpenAI兼容网关统一计费
- **`sanjianke-knowledge-qa`** 知识库问答搭建·向量检索加OpenAI兼容模型网关统一接入

### 短剧二创（2）

- **`duanju-remix-playbook`** 三剪客 · 短剧二创作业手册
- **`duanju-rights-compliance`** 三剪客 · 短剧二创授权与合规自查

### 设计（2）

- **`sanjianke-comfyui`** 三剪客 · 节点式出图流水线 · 衍生指南
- **`sanjianke-stable-diffusion-webui`** 三剪客 · 本地出图工作台 · 衍生指南

### OCR（2）

- **`sanjianke-paddleocr`** 三剪客 · 中文 OCR 与版面分析 · 衍生指南
- **`sanjianke-rapidocr`** 三剪客 · 轻量多语言 OCR · 衍生指南

### 短剧（1）

- **`short-drama-factory`** 三剪客 · AI 短剧工厂出片全流程

### AI 客户端（1）

- **`sanjianke-ai-chat-ui`** AI聊天客户端接国产大模型·一个Key换75个模型接入配置

### Java（1）

- **`sanjianke-java-agent-kit`** Java接大模型与Agent·OpenAI兼容网关直连75模型包

### 大模型（1）

- **`sanjianke-deepseek-cloud`** DeepSeek全系云端直连·免部署一个Key切换调用大模型

### 聊天机器人（1）

- **`sanjianke-chatbot-builder`** 聊天机器人接大模型·多平台机器人用国产模型回话方案

### AI插件市场（1）

- **`aigc-market`** AI图片视频音乐语音配音数字人口播换装超分剪辑全能创作插件市场

### ai-api（1）

- **`one-key-ai-gateway`** 三剪客 · 国产大模型一键调用统一路由

### xiaohongshu（1）

- **`xhs-daihuo-live-kit`** 三剪客 · 小红书带货直播作战包

### 教育学习（1）

- **`sanjianke-ai-classroom-kit`** 三剪客 · 多智能体互动课堂 · 衍生指南

### 教育（1）

- **`sanjianke-labuladong`** 三剪客 · 算法题解语料库 · 衍生指南

### MCP（1）

- **`sanjianke-mcp-servers`** 三剪客 · MCP 官方服务器集 · 衍生指南

### Agent（1）

- **`sanjianke-openhands`** 三剪客 · 自主编码 Agent · 衍生指南

### RAG（1）

- **`sanjianke-ragflow`** 三剪客 · 深度文档理解 RAG · 衍生指南

### IT 运维与安全（1）

- **`sanjianke-web-audit-kit`** 三剪客 · 网站质量审计 · 衍生指南

## 关于 api.a7w.cn

本仓库中涉及大模型推理、算力或需要模型服务密钥的技能，默认指向 [算力集市 api.a7w.cn](https://api.a7w.cn/)：一个 Key 调用全部 AI 算力。
也可以换成任何兼容的官方 Key，技能正文里写明了如何切换。

## 许可

- 三剪客原创内容：MIT，见 [LICENSE](LICENSE)
- 第三方开源项目的名称、商标与仓库归属各自所有者；本仓库只提供原创使用指南
- 衍生包的上游项目与仓库见 [THIRD-PARTY.md](THIRD-PARTY.md)
- **注意**：部分上游项目带商用限制（非商用许可 / AGPL / 禁止对外提供 SaaS）。
  本仓库内容不受影响，但你实际使用上游软件前请自行核对上游许可，
  清单见 [THIRD-PARTY.md](THIRD-PARTY.md) 的「上游许可提示」一节。

## 联系

- 技术微信：**9872659**
- 算力集市：https://api.a7w.cn/
- AI 插件市场：https://aigc.a7w.cn/
