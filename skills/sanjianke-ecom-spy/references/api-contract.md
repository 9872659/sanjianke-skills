# 带货素材侦察 —— 接口契约（实测原文）

本文所有「实测」均为 **2026-11-07 只读实测**：`GET /api/v1/pricing`、`GET /api/v1/apps`、
`GET /api/v1/models`、`GET /user/balance`、`GET /user/balance/logs`、`GET /api/v1/tasks/<假id>`。
**本轮没有发过一次 POST**，花费 0 点（余额前后一致，见文末）。

参数表来自该应用 `params_schema` 的存档（`code / required / description` 逐字照抄），
其中 `required` 在 schema 里是字符串 `"1"` / 空，本包按「有值即必填」处理。

---

## 一、调用形态

```
POST https://api.a7w.cn/api/v1/apps/watermark_removal/<接口code>
Authorization: Bearer <你的 Key>
Content-Type: application/json
```

- **同步**：`call_type = 1`，直接返回结果。没有 `task_id`，不需要轮询。
  （家族里别的包「提交 + 轮询」的写法在本包不适用，所以没有 `--wait` / `--every` / `status`。）
- 应用本体：`GET /api/v1/apps` 实测 `{"id":4,"name":"水印消除","code":"watermark_removal",
  "driver_code":"watermark_removal","billing_mode":1,"category_name":"其他"}`，`apis` 共 **8** 个。

---

## 二、8 个接口的参数表（`params_schema` 原文）

### 1. `douyin_search_video` · 抖音搜索 · 子命令 `dy-search` / `hunt --platform dy`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `keyword` | string | **是** | 搜索关键词 |
| `page` | string | 否 | 页码 |
| `searchId` | string | 否 | 搜索会话标识，翻页时使用（也可用 `search_id`） |

### 2. `douyin_video_detail` · 抖音视频详情 · `dy-video`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `videoId` | string | **是** | 短视频作品 ID，也可用 `video_id` |

### 3. `douyin_user_video_list` · 抖音用户作品 · `dy-user`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `secUid` | string | **是** | 用户 secUid（短视频侧），也可用 `sec_uid` |
| `maxCursor` | string | 否 | 翻页游标，也可用 `max_cursor` |

### 4. `xhs_search_note` · 小红书笔记搜索 · `xhs-search` / `hunt --platform xhs`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `keyword` | string | **是** | 搜索关键词 |
| `page` | string | 否 | 页码，默认 1 |
| `sort` | string | 否 | `general` / `popularity_descending` / `time_descending` / `comment_descending` / `collect_descending` |
| `noteType` | string | 否 | 笔记类型：`_0` 通用 / `_1` 视频 / `_2` 图文（也可用 `note_type`） |
| `noteTime` | string | 否 | 发布时间筛选（按上游约定传值，也可用 `note_time`） |

### 5. `xhs_note_detail` · 小红书笔记详情 · `xhs-note`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `noteId` | string | **是** | 笔记 ID（与分享链接中 id 一致），也可用 `note_id` |

示例值（schema 原文）：`69db4372000000002103a442`

### 6. `xhs_user_detail` · 小红书用户详情 · `xhs-user`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `userId` | string | **是** | 小红书用户 ID（userid），也可用 `user_id` |

### 7. `xhs_user_note_list` · 小红书用户笔记 · `xhs-user-notes`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `userId` | string | **是** | 笔记侧用户 ID（userid），也可用 `user_id` |
| `cursor` | string | 否 | 翻页游标，取自上一页笔记项 |
| `lastCursor` | string | 否 | 上一页末条目的游标，也可用 `last_cursor` |

### 8. `remove` · 去除水印 · `strip`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `url` | string | **是** | 短视频分享链接（示例 `https://example.com/s/xxxxx/`） |

上游内部路径分别是 `/zyf.php`（remove）与 `/justone/<code>`（其余 7 个），
对外统一走 `POST /api/v1/apps/watermark_removal/<code>`，**不要直连上游路径**。

---

## 三、价格（`GET /api/v1/pricing` 原文，逐字）

```json
"/api/v1/apps/watermark_removal/*": {
  "mode": "flat", "cost": 100, "markupPercent": 0,
  "note": "去水印/分享链解析：固定 100 点/次（上游按请求 20 点，失败亦计）"
}
"/api/v1/apps/watermark_removal/remove": {
  "mode": "flat", "cost": 100, "markupPercent": 0,
  "note": "去水印/分享链解析：固定 100 点/次（上游按请求 20 点，失败亦计）"
}
"*": {
  "mode": "flat", "cost": 0, "markupPercent": 100, "minPoints": 50,
  "note": "未单独定价的接口：对外 = 上游实际点数 × 2，单笔保底 50 点"
}
```

**结论**：8 个接口全部命中 `watermark_removal/*` 这条 **flat 100 点/次** 的规则。

- 同一个价：搜一条、搜一百条、看详情、取地址，都是 100 点。
- 与素材时长、返回条数无关。
- `note` 里的「上游按请求 20 点」是平台侧成本，「**失败亦计**」意思是上游对失败请求也计点 ——
  本包据此**不做任何 POST 探针**（见第五节）。
- 应用级还有 `submit` / `create` 两条 `cost:0` 的规则，但该应用**没有**这两个接口
  （`GET /api/v1/apps` 的 8 个 code 里没有它们），属历史遗留键，用不到。

出图线实价（同一份 `/api/v1/pricing`，供 `cover` 报价）：

| 路径 | 单价 | 备注 |
|---|---|---|
| `/api/v1/apps/nano_banana/*` | **72 点/次** | AI 商品图固定 72；带 `views[]` 时按 25 点 × 视角数 |
| `/api/v1/apps/aigc_qwen_image/generate/index` | 78 点/次 | 通用出图 |
| `/api/v1/apps/aigc_wan_image/generate/index` | 203 点/次 | 写实场景 |
| `/api/v1/apps/aigc_photo_restore/*` | 105 点/次（1K） / 203（2K） | 老照片修复 |

---

## 四、返回体形态

文档原文（`api_doc` 字段）：**「成功时业务数据位于响应 `result.data`」**。
网关统一信封是 `{"code":1,"msg":"success","data":{…}}`，两者叠起来可能有两种落点：

```
{"code":1,"msg":"success","data":{"result":{"data":{…}}}}      ← 文档口径
{"code":1,"msg":"success","data":{…}}                          ← 网关口径
```

**本轮 0 点，没有实跑成功响应，所以精确形状没有被实测确认。** 本包的策略是：

1. 成功判据只看信封：HTTP 200 且 `code ∈ {1,200}`；
2. 业务数据按 `result.data` → `data` → `result` → 原对象的顺序取第一个 dict / list；
3. 条目提取是**递归容错**的：一个 dict 只要有标题类字段（`desc` / `title` / `display_title` /
   `caption` / `content`）并且有 ID 类字段（`aweme_id` / `note_id` / `video_id` / `id`…）
   或统计块（`statistics` / `stats` / `interact_info`），就当成一条作品收下；
4. 互动数认这些键：赞 `digg_count` / `liked_count` / `like_count`，藏 `collect_count` /
   `collected_count`，评 `comment_count` / `comment_count`，转 `share_count`；
5. 时长优先 `duration`，其次 `video.duration`；大于 1000 视为毫秒，自动除以 1000。

原始响应**整份落盘**在快照里（`raw` 字段），解析不到条目时 `_print_collect` 会打印前 800 字，
`--json` 能拿到完整 `raw`。需要按真实形状补字段时，改 `norm_item()` 一处即可。

---

## 五、探针纪律：doctor 只发 GET

规则 note 写着「失败亦计」。也就是说，用一个「合法前缀 + 缺必填参数」的 POST 去探端点，
**会被参数校验拦下，但那一笔仍可能按次计 100 点**。所以本包：

| doctor 检查项 | 端点 | 期望 |
|---|---|---|
| Key 有效 + 余额 | `GET /user/balance` | 200 且含 `available_points` |
| 模型目录 | `GET /api/v1/models` | 200 且 `data` 非空 |
| 应用在架 + 8 接口齐全 | `GET /api/v1/apps` | `code=watermark_removal` 且有全部 8 个 code |
| 单价与本地一致 | `GET /api/v1/pricing` | `watermark_removal/*` 的 `cost` = 100 |
| 任务查询路由 | `GET /api/v1/tasks/sanjianke-ecom-probe` | 200 + `{"code":0,"msg":"任务不存在"}` |
| 流水可达 | `GET /user/balance/logs?limit=1` | 200 且 `logs` 是 list |

**端点存在性的证明方式**从「POST 一轮看报错码」换成「GET 名单看 code 齐不齐」——
名单是平台自己回的，8 个 code 一个不缺，等价于端点都在册。

---

## 六、本轮只读实测的原始返回

### 6.1 `GET /user/balance`（探针前后各一次，完全一致）

```json
{"available_points":999997393482.2579,"points":999997393482.2579,"frozen":0,
 "member_points":0,"yuan":9999973934.82,"rate":100,"currency":"points",
 "note":"本平台按用户/Key 隔离统计，非上游租户级数字"}
```

前后两次逐字相同 ⇒ **本轮花费 0 点**。

### 6.2 `GET /api/v1/apps`（96,754 字节，22 个应用）

```json
{"id":4,"name":"水印消除","code":"watermark_removal",
 "description":"支持抖音、快手、小红书等主流短视频平台，输入分享链接即可获取无水印视频地址。",
 "driver_code":"watermark_removal","billing_mode":1,"category_id":5,
 "category_name":"其他","category_code":"other","tenant_sort":0}
```

`apis` 8 个，code 依次为：`remove`、`xhs_note_detail`、`xhs_user_note_list`、
`douyin_user_video_list`、`xhs_user_detail`、`douyin_video_detail`、`douyin_search_video`、`xhs_search_note`。
全部 `method=POST`、`call_type=1`。

### 6.3 `GET /api/v1/tasks/sanjianke-ecom-probe`

```json
{"code":0,"msg":"任务不存在","data":null}
```

### 6.4 `GET /api/v1/models`

`HTTP 200`，522,714 字节，`{"object":"list","data":[{"model_code":"muse-video",…}]}`。

### 6.5 `GET /user/balance/logs?limit=6`

```json
{"total":7893,"inPoints":275085.5268,"outPoints":681321.4685,
 "netPoints":-406235.9417,"balanceMoving":-176068.2217}
```

最近 6 条都是别的包（`voice_tts/list_voices` 的冻结 / 退款）留下的，
没有一条 `watermark_removal` ⇒ 本轮确实一次都没调用本包接口。

对账口径：调用本包后流水里会出现 `sync:/api/v1/apps/watermark_removal/<code>`，每次 `-100`。
