# 注册、领 Key 与配置

## 一、注册与领 Key

1. 打开 **[算力集市 api.a7w.cn](https://api.a7w.cn/)**，注册账号（新用户有赠送点数，
   可以先免费试跑几条）。
2. 按提示完成实名认证。
3. 进 **用户中心 → API 密钥**，创建一个 Key（形如 `sk-...`）。

> **Key 等同于余额。** 不要写进代码、不要提交进 Git 仓库、不要发给别人。

---

## 二、把 Key 配到本机

三种方式任选一种，优先级从高到低：

```bash
# 1) 存到配置文件（推荐，权限 600）
python3 scripts/a7w.py login --key sk-你的key

# 2) 环境变量
export A7W_API_KEY=sk-你的key          # Windows: $env:A7W_API_KEY="sk-你的key"

# 3) 单次传参
python3 scripts/a7w.py call chat completions --key sk-你的key --body '{...}'
```

配置文件路径：`~/.a7w/config.json`。

验证：

```bash
python3 scripts/a7w.py whoami
```

---

## 三、在代码里用

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://api.a7w.cn/api/v1",
    api_key=os.environ["A7W_API_KEY"],      # 从环境变量读，不硬编码
)
```

自己的项目里建议用 `.env` + 环境变量管理工具，别把 Key 写进源码。

---

## 四、治理能力

| 能力 | 说明 |
|---|---|
| **Key 级 quota** | 每个 Key 可单独设消费上限，打满后该 Key 调不动（与账号余额是两回事） |
| **IP 白名单** | 限制 Key 只能从指定来源调用 |
| **速率限制** | 按 Key 限速，撞限会返回 429 |
| **用量流水** | 可导出，便于按项目 / 客户分别对账 |
| **充值** | 点数永久有效；**调价不追溯已充余额** |

---

## 五、网络与排错

- 需要能访问 `https://api.a7w.cn`（内网 / CI 请放行该域名）。
- 报 401：Key 无效或过期 → 重新 `login`。
- 报 402：先分清是账号余额不足还是 Key 的 quota 打满。
- 报 404：核对应用 / 模型代号拼写，代号来自接口返回。
- 报 429：降并发，等队列消化后重试。

细节见 `通用说明.md` 与 `api-openai-compat.md`。
