# GPT Image 2.6 出图台 —— 排错

**先跑 `python3 scripts/run.py doctor`** —— 免费、不扣费，能一次排掉一半问题。

---

## 一、Key 相关

### `失败：没有 API Key`（exit 2）

三处都没读到。按优先级检查：

1. `--key sk-...`
2. `echo $env:A7W_API_KEY`（PowerShell） / `echo $A7W_API_KEY`（bash）
3. `~/.a7w/config.json` 里的 `{"key": "sk-..."}`

最省事：

```bash
python3 scripts/a7w.py login --key sk-你的key
```

### `拉模型清单失败（HTTP 401）`

Key 本身的问题。去 [api.a7w.cn](https://api.a7w.cn/) 重新创建。

---

## 二、出图失败

### `出图失败（HTTP 422）prompt: String should have at least 1 character`

`--prompt` 是空的。**注意**：`--image` 不能代替 `--prompt`，改图也要写清"改成什么"。

### `出图失败（HTTP 400）… size …`

尺寸不合规。四条硬约束：

- 宽高都是 **16 的倍数**
- 长边 / 短边 **≤ 3:1**
- 单边 **≤ 3840**
- 总像素 **655,360 – 8,294,400**

**本包在本地就校验这四条**，正常不会走到上游；如果走到了，说明你的 `--size` 是 `1k`/`2k`/`4k`
之外的写法但恰好通过了本地校验 —— 请改用标准写法。

### `出图失败（HTTP 400）n: expected an integer in [1, 4]`

`--n` 只能 1–4。本包本地也会拦。

### `出图失败（HTTP 400）Transparent backgrounds are only supported with 'png' or 'webp'`

`--background transparent` 不能和 `--output-format jpeg` 或 `--gif` 一起用。

### `出图失败（HTTP 404）The model 'xxx' does not exist or you do not have access to it`

模型名写错，或者你的 Key 没有这个模型的权限。用 `python3 scripts/run.py models` 查在架模型。

### 响应里没有图，但 HTTP 200

本包会打印原始返回。常见原因：

- 上游内容审核拦了（会带说明，**不扣费**）
- 返回结构变了

**看 `data` 数组长度**：本包打印「请求 N 张 / 实际返回 M 张」。M 为 0 就是没出图，**不会扣费**。

---

## 三、⚠️ 最坑的一个：图出了，但不是你要的模型

**症状**：出图成功、也能下载，但**风格/质量明显不是 2.6**，而且**扣了 72 点而不是 6 点**。

**原因**：端点路径写错了。

```
✅ POST https://api.a7w.cn/api/v1/images/generations   ← 认 model
❌ POST https://api.a7w.cn/v1/images/generations       ← 忽略 model，落到网关默认应用
```

**实测**：往错误的那条路传 `gpt-image-2.6`、甚至传 `no-such-model-xyz`，
**两次都路由到 `nano_banana`（72 点/次）**，而且不报错。

**怎么确认自己走对了**：跑 `doctor`，第三项必须是

```
✓ 文生图端点可用（422 即正确）   HTTP 422 prompt: String should have at least 1 characte
```

**本包默认就用正确的路径**，所以正常情况下不会踩到。

---

## 四、图出来了但打不开 / 403

### 用 `--want-url` 拿到链接后自己下载，返回 403

文档写明：**用 Python 标准库 `urllib` 下载必须自设 `User-Agent`**，默认值会被拒 403。
`requests` / `httpx` / `curl` / 浏览器不受影响。

```python
import urllib.request
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
data = urllib.request.urlopen(req, timeout=180).read()
```

### 链接 404 了

两个原因：

1. **超过约 3 小时**，链接失效
2. **给链接追加了查询参数** —— 文档明确「原样使用，追加查询参数会 404」

**本包默认用 `b64_json` 并直接落盘成文件**，不走链接，所以不受影响。
只有你显式加 `--want-url` 才会拿到链接。

---

## 五、花钱相关

### `失败：预计 6 点超过 --budget 5 点`（exit 5）

闸门在工作。调大 `--budget` 或减少 `--n`。

**`--budget` 单位是「点」**（1 元 = 100 点），默认 500 点（5 元）。

### `失败：这会真实出图并扣约 6 点`（exit 4）

缺 `--yes`。**故意的**：出图要花钱，必须显式确认。

想先看请求：

```bash
python3 scripts/run.py gen --prompt "..." --dry-run
```

### 实际扣费比预估多

**不可能超过 `6 × n`**（文档：按张计费，与尺寸/质量/格式无关）。

但**可能比预期少**：`n=2` 只回 1 张就只收 1 张。本包会打印「请求 N 张 / 实际返回 M 张」
和「计费 X 点」。

### 请求失败了，会扣钱吗？

**不会。** 文档明确：参数错误、请求失败、没返回图片 → **不扣费**；内容审核拒绝也不扣费。

**只有一种例外**：客户端中途断开或流式中断 → **仍按请求张数计费**。

---

## 六、慢 / 超时

- 一张图通常 **20–50 秒**；GIF 更久，**最长见过约 130 秒**
- 本包默认超时 **240 秒**，可用 `--timeout 400` 调大
- 文档建议客户端超时设 **180 秒以上**

### 超时了怎么办

**同步调用**，没有任务 id 可查。直接重跑会**再扣一次 6 点**。

**建议**：先确认网络能稳定访问 `api.a7w.cn`，再把 `--timeout` 调大。

---

## 七、GIF 相关

### 要 GIF 结果只出了静态 PNG

文档说明这**是正常现象**：「偶尔只出静态图（返回 PNG，`output_format` 写 `png`）」。

### GIF 的尺寸不对

**正常**：`size`、`frame_count`、`frame_duration_ms` **对 GIF 不生效**，
尺寸和帧数由模型决定（实测约 8–16 帧，边长 170–900 像素）。

### 想用 SVG

**不支持。** 传 `output_format=svg` 返回 400；提示词要 SVG 也只返回位图。

---

## 八、还想更省事

```bash
python3 scripts/run.py doctor && python3 scripts/run.py gen --prompt "..." --yes
```

`doctor` 通过才继续 —— 省掉一次白跑。

---

## 九、联系

见 SKILL.md 的「## 联系我们」 时说一下是从 `sanjianke-gpt-image` 找过来的，
直接给你配套的 API Key 与能跑的示例。
