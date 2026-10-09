# 部署与配置

这份文件面向一件事：**把一套 B/S 架构的 AI 短剧创作台从空机器装到能出片**。
后端是常驻服务，前端是构建好的静态资源，生成任务交给外部模型异步跑，
最后一步合成落回本机自己做的多媒体工具上。

组织方式是「一步一步来，每步都能验收」。**上一步没验收通过，不要往下走**——
这类系统的坑大多在后面才炸，前面偷的懒会在批量出片时一次还清。

---

## 一、先看清这套系统的形状

典型的部署形态是四层：

```
浏览器（前端静态资源）
    ↓ HTTP
应用服务（业务逻辑 + 任务调度）
    ↓                        ↘
数据库 / 缓存            外部模型服务（异步，返回任务号）
    ↓
多媒体工具（本机进程，负责拼接、字幕、音画对齐）
    ↓
对象存储 / CDN（成品与素材）
```

从这张图里能读出三个必须先接受的结论：

1. **合成发生在你机器上**。所以这台机器要留出 CPU 余量，而且多媒体工具必须装在
   服务进程够得着的位置——不是「装过了」就行。
2. **模型调用是异步的**。你拿到的是一个任务号，不是结果。任务状态表、轮询、超时
   这三样是必需品，不是优化项。
3. **素材必须进对象存储**。这不是可选项；省了这一层，素材会先堆满本地盘，
   再让你在凌晨三点去清理。

---

## 二、按出片量决定买什么机器

不要按预算选，也不要按感觉选，按**每月要出多少集**选：

| 档位 | 月产出 | CPU | 内存 | 系统盘 | 数据盘 | 显卡 |
|---|---|---|---|---|---|---|
| 试水 | ≤ 20 集 | 4 核 | 8 GB | 40 GB | 100 GB | 不需要 |
| 常规 | 20–100 集 | 8 核 | 16 GB | 60 GB | 500 GB | 不需要 |
| 高产 | 100–300 集 | 16 核 | 32 GB | 100 GB | 1 TB+ | 不需要 |
| 自建推理 | 不限 | 16 核以上 | 64 GB 以上 | 100 GB | 2 TB 以上 | 看模型 |

**这里有个反直觉的点**：只要模型全部走外部 API，这台机器**根本不需要显卡，CPU 才是瓶颈**。
拼接、烧字幕、对齐音画，吃的是 CPU。配一台「显卡拉满、CPU 很弱」的机器是最常见的浪费；
只有当你确实要把图像或视频模型放到本地推理时，显卡才开始有意义。

**带宽**单独算一笔：用户预览成品、CDN 回源，走的都是流量。
面向公网的话，建议对象存储前面挂一层 CDN，并按真实码率估算（用 `scripts/cost_estimate.py`）。

---

## 三、装依赖

### 3.1 版本要对齐

| 组件 | 版本要求 | 干什么用 | 怎么验收 |
|---|---|---|---|
| 运行时 | 与后端语言匹配的 LTS | 跑应用服务 | 能打印出版本号 |
| 构建工具 | 与运行时配套 | 编译打包 | 能输出构建成功 |
| 前端运行时 | Node.js 18 LTS 及以上 | 构建前端资源 | `node -v` |
| 数据库 | MySQL 8.0 及以上 | 业务数据 | `mysql --version` |
| 缓存 | Redis 6 及以上 | 会话、限流、任务锁 | `redis-cli ping` 应返回 PONG |
| 多媒体工具 | FFmpeg 稳定版 | 合成、转码、字幕 | `ffmpeg -version` |

**后端语言与运行时版本，必须和项目自己声明的版本一致。** 版本不对时，
编译器吐出来的错误信息通常完全读不懂，先对齐版本能省下一整天。

### 3.2 Linux

```bash
# 系统包方式装数据库、缓存与多媒体工具
sudo apt update
sudo apt install -y mysql-server redis-server ffmpeg

# 验证三件套
mysql --version && redis-cli ping && ffmpeg -version | head -n 1
```

前端运行时建议用版本管理器（nvm 这类）装，系统包仓库里的版本往往偏旧。

### 3.3 Windows

```powershell
# 用包管理器安装，省去手工配 PATH
winget install OpenJS.NodeJS.LTS
winget install Gyan.FFmpeg

# 装完必须重开终端再验证，否则 PATH 未刷新
node -v
ffmpeg -version
```

数据库和缓存在 Windows 上建议用官方安装包，或者干脆放进 WSL 跑。
**FFmpeg 要特别确认它在服务进程的 PATH 里**：服务以系统账户启动时，
当前用户级 PATH 通常不生效——这是 Windows 上「明明装了却找不到 ffmpeg」的头号原因。

---

## 四、把数据库建对

### 4.1 字符集是第一优先级

中文标题、台词、提示词，全都得靠 `utf8mb4`。用默认字符集建库，等发现乱码时
只能重建表，那个代价比一开始多打两行字大得多。

```sql
-- 建库：显式指定字符集与排序规则
CREATE DATABASE drama_studio
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

-- 建专用账号，不要用 root 跑应用
CREATE USER 'drama_app'@'%' IDENTIFIED BY 'REPLACE_WITH_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON drama_studio.* TO 'drama_app'@'%';
FLUSH PRIVILEGES;
```

### 4.2 连接串

```ini
jdbc:mysql://127.0.0.1:3306/drama_studio
  ?useUnicode=true
  &characterEncoding=utf8
  &useSSL=false
  &serverTimezone=Asia/Shanghai
  &allowPublicKeyRetrieval=true
```

`serverTimezone` 一定要写。不写的话，时间字段可能整体偏移几个小时，
而这种偏差在出片流程里很难第一眼看出来。

### 4.3 用一句中文验收

```sql
-- 插一条中文，再读回来，字符不能变成问号
INSERT INTO drama_studio.t_probe (title) VALUES ('测试·中文标题');
SELECT title FROM drama_studio.t_probe;
```

读回来是问号，说明字符集或连接参数还没对，**这时候停下来先把这件事解决**。

### 4.4 四类表必须齐

表名可以不同，功能不能缺：

| 类别 | 干什么 | 缺了会怎样 |
|---|---|---|
| 作品与集 | 组织内容层级 | 管不了多集项目 |
| 分镜 | 最小创作单元 | 没法逐个镜头控制 |
| 素材与成品 | 记录生成结果地址 | 素材找不到，也复用了 |
| 任务日志 | 异步任务状态 | 失败无法重试，也定位不了原因 |

看到候选项目里**没有「任务日志」这类表**，就要知道它的异步生成是个黑盒。
建议上线生产前自己补一张状态表。

---

## 五、密钥放在哪

**一条铁律：任何密钥都不进代码库。**

| 密钥 | 放哪 | 绝不能 |
|---|---|---|
| 数据库口令 | 环境变量或密文配置 | 写进配置文件提交上去 |
| 模型 API Key | 环境变量 / 加密存储 | 出现在前端、出现在日志里 |
| 对象存储 AK/SK | 环境变量 | 硬编码 |
| 会话与签名密钥 | 环境变量 | 用示例默认值 |

```bash
# Linux / macOS：写入当前用户环境，重启终端生效
export DRAMA_DB_PASSWORD='REPLACE_ME'
export DRAMA_AI_API_KEY='REPLACE_ME'
export DRAMA_OSS_ACCESS_KEY_ID='REPLACE_ME'
export DRAMA_OSS_ACCESS_KEY_SECRET='REPLACE_ME'
```

```powershell
# Windows：写用户级环境变量
[Environment]::SetEnvironmentVariable('DRAMA_AI_API_KEY','REPLACE_ME','User')
```

**上线前搜一遍**：在代码库里搜 `key`、`secret`、`password`、`token`，
确认没有真凭据被提交上去。示例值要一眼就看得出是占位符。

如果项目把密钥存在数据库里，先确认是不是加密存的；明文存的话，
至少限制数据库的访问来源，并把读取配置的接口单独审计。

---

## 六、模型怎么接

四类能力**分别配**，不要图省事只配一家：

| 能力 | 用在哪儿 | 配置时要留意 |
|---|---|---|
| 文本 | 拆镜头、写提示词、写台词 | 长文本截断策略、上下文长度 |
| 图片 | 场景图、角色图、参考图 | 能传几张参考图、角色一致性 |
| 视频 | 图生视频、镜头片段 | 异步，必须配轮询和超时 |
| 配音 | 台词转语音 | 音色库够不够、有没有情感参数 |

### 6.1 先确认供应商能不能换

架构好不好，有个很省事的检验办法：

> 把现在这家供应商的调用代码注释掉，换另一家要改几个文件？
> 只动适配层 → 架构还行；要改业务逻辑 → 有风险，越早重构越便宜。

### 6.2 混着用，别强求统一

为了「只用一家」而牺牲效果，通常不划算。常见的混法：

- 文本量大，挑便宜且稳定的
- 图片挑角色一致性好的——短剧最怕角色一集一个样
- 视频挑时长和分辨率够用的，它占成本大头
- 配音挑音色贴合角色的

配完之后**每一类都要真打一次**。不要等到批量生产的那天才发现某一类压根没配通。

### 6.3 异步任务必须有的三件事

1. **任务号落库**：提交成功就立刻记下外部任务号和本地记录的对应关系
2. **轮询带退避**：死循环式定频轮询会被限流
3. **超时与重试上限**：没有上限的重试，等于没有上限的预算

---

## 七、对象存储与 CDN

| 配置项 | 怎么配 | 常犯的错 |
|---|---|---|
| 区域 / 端点 | 跟服务器同区域，省回源费 | 跨区，又慢又贵 |
| 存储桶 | 素材桶和成品桶分开 | 混用，权限越来越难管 |
| 访问域名 | 绑 CDN 做加速 | 直接把源站地址对外 |
| 跨域（CORS） | 只放开前端所在域名 | 图省事写 `*` |
| 生命周期 | 给中间素材设过期清理 | 不设，存储一直涨 |

**算一笔账**：参考图、废弃镜头这类中间素材，往往比成片大得多。
按「中间素材留 30 天、成片长期保留」设生命周期，能省掉相当可观的一笔。

---

## 八、让服务常驻，把前端发布出去

### 8.1 后端交给系统服务托管

后端不要跑在交互式终端里。用系统服务托管，才能开机自启、崩了自动拉起来。

```ini
# /etc/systemd/system/drama-studio.service
[Unit]
Description=Drama Studio Backend
After=network.target mysql.service redis-server.service

[Service]
Type=simple
User=drama
WorkingDirectory=/opt/drama-studio
EnvironmentFile=/etc/drama-studio/env
ExecStart=/opt/drama-studio/bin/start.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now drama-studio
sudo systemctl status drama-studio
```

**`EnvironmentFile` 才是密钥进入服务进程的正确通道。** 直接写进 unit 文件，
任何能读到这个文件的人都能看到你的密钥。

### 8.2 前端构建

```bash
# 构建产物交给 Web 服务器，不要用开发服务器对外
npm ci
npm run build
# 产物通常在 dist/ 或 build/ 目录
```

**开发模式的服务绝对不能对外**——既没有性能优化，本身也是安全隐患。

### 8.3 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name drama.example.com;

    # 前端静态资源
    root /opt/drama-studio/web;
    index index.html;

    # 单页应用回退
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 接口转发到后端
    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # 生成类接口耗时长，必须放宽超时
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
```

**两个必踩的坑**：

- 单页应用少了 `try_files` 回退，用户一刷新子路由就是 404
- 生成类接口不放宽超时，默认 60 秒会把长任务直接掐断

### 8.4 跨域

只要前后端不在同一个域，这一项就必须配。上线环境里**允许来源要逐个域名写清楚**，
通配符不能用；另外确认预检请求（OPTIONS）能得到正确响应。

---

## 九、装完先验收一个镜头

环境装好之后，**第一个动作是跑单镜头，不是直接开批量**：

- [ ] 能创建作品与集
- [ ] 能录入一段剧情并拆出分镜
- [ ] 至少一个分镜能生成场景图 / 角色图
- [ ] 参考图能正常预览（说明对象存储通了）
- [ ] 至少一个分镜能生成视频片段
- [ ] 台词能生成配音，且能试听
- [ ] 单镜头能完成合成，产出可播放文件
- [ ] 多镜头能整集拼接，音画时长基本对齐
- [ ] 后台任务列表里能看到上面每一步的状态流转
- [ ] 失败任务能重试并成功

**这十项里，「音画时长对齐」最值得盯。** 配音时长和视频时长一般不会刚好相等，
常规做法是补静音，或者把最后一帧延长。对齐策略做得糙，成片就会跳音或画面卡住。
这个问题的代价完全是时间差：单镜头阶段发现，损失是几分钟；批量阶段才发现，损失是几十集的生成费。

> 平台侧的这四类算力已经可以直接用本包的脚本打：
> `python scripts/run.py image / video / voice`，一条命令一个镜头。
> 装环境之前先确认外部链路是通的，能把「装错了」和「接口没通」这两类问题分开。

---

## 十、部署期问题速查

| 症状 | 先查哪儿 |
|---|---|
| 服务起不来 | 端口被占、数据库连不上、环境变量没加载 |
| 中文变问号 | 建库字符集、连接串里的 `characterEncoding` |
| 找不到 ffmpeg | 服务账户的 PATH；改成绝对路径 |
| 调模型超时 | 网关超时设置；确认这个接口是不是异步 |
| 素材预览不了 | 对象存储跨域、域名能不能被公网访问 |
| 长任务中途断了 | 反向代理超时、轮询超时设得太短 |
| 前端刷新 404 | 少了单页应用回退配置 |
| 磁盘掉得飞快 | 中间素材没设生命周期、日志没切割 |

剩下的运维、账单与合规问题，见 `references/ops-and-compliance.md`。
