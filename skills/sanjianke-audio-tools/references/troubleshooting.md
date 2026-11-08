# 排错：按报错找原因

先跑一条 `python3 scripts/run.py doctor`。它 10 项检查全过，说明 Key、价目表、
三个接口、上传口、任务查询、流水都是通的，问题在参数或素材上；有 `×` 的那一项
就是入口本身的问题。

---

## 一、按返回码对号

| 返回 | 原文 | 原因 | 怎么办 |
|---|---|---|---|
| `400 empty_url` | `videoUrl 不能为空` | 提交 `interp` 没带视频地址 | 先 `upload --file 片子.mp4`，用返回的地址 |
| `400 url_not_allowed` | `videoUrl 必须是本站（vr.a7w.cn）、本站七牛（cdn2.jiujiushuyuan.cn/vr/）或本站上传接口返回的地址（oss.gpu.likeadmin.cn/openapi/）` | 地址不在白名单 | 换 `upload` 返回的地址；只有确知要直连才加 `--allow-any-url` |
| `400` / `422` + `input.xxx` | 字段类型或枚举不对 | 参数写错 | 按提示改。这一层不建任务、不扣点 |
| `400 tool_not_launched` | 该档位未开放 | 上游下线了这档 | `interp` 遇到过就改用本机 ffmpeg（见 `二创链路.md`） |
| `200 {"code":0,"msg":"应用或 API 不可用或未配置价格"}` | 应用层兜底话术 | 应用代号或 API code 拼错 | 回到 `catalog` 抄路径，必须是 `/api/v1/apps/music_generation/<code>` |
| `404` + HTML | 网关 SPA 页 | 该前缀下没有这个端点 | 同上；`vox` / `mashup_lyrics` / `upload_audio` 只在 `music_generation` 名下 |
| `HTTP 500` | 上游偶发 | 上游抖动 | 重试一次；失败任务全额退回，净 0 点 |
| `HTTP 401` / `403` | `Unauthorized` | Key 不对或没权限 | 换 Key；`doctor` 第一项就会挂 |

## 二、提交成功但拿不到产物

| 现象 | 原因 | 怎么办 |
|---|---|---|
| 回了 `task_id`，`status` 一直是 `processing` | `vox` 异步，要等 | `status --task-id xxx` 再查；一般 30 秒到几分钟 |
| `status` 说「任务不存在」 | 拿错 ID 或任务在另一条线 | 通用视图是 `/api/v1/tasks/<id>`；视频线补 `--video` 查 viapi 视图 |
| 产物链接打不开 | 链接有时效 | 拿到就转存；`upload` 的地址约 24 小时，成片更短 |

## 三、钱包被动过一下，但没少钱

```
20:57:07  charge  -60  reserve_sync:/api/v1/apps/music_generation/<code>
20:57:11  refund  +60  refund:sync_error:/api/v1/apps/music_generation/<code>
```

- 本包**不做这种探针**：`doctor` 对三个音频接口一次都不 POST，在架与否用
  `GET /api/v1/apps` + `GET /api/v1/pricing` 证明
- 真看到了就等 `refund` 那一笔，或跑 `status` 看 `refund` 字段

## 四、价格对不上

| 现象 | 解释 |
|---|---|
| `cost` 说 42 点，账单是别的数 | 42 是「上游 14 点 × 3」的估，真实值看返回体 `data.usage.points_cost` |
| `create` 显示「待实测」 | 本账号还没跑过 `create`，价随 `type` 变，不编数字 |
| `interp` 显示「待验证」 | 价目表有 25 点/秒，线上档位说明写过「已下线」，真跑一条才知道结不结算 |
| 按秒档被多扣 | 按秒档先按 `duration` 冻结，完成后按实际时长结算；`duration` 给太小会补扣 |

## 五、中文控制台乱码或崩掉

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `UnicodeEncodeError: 'gbk' codec` | Windows 管道用 cp936 输出 | 本包已 `reconfigure(errors="replace")` + `safe`；自建脚本也照做 |
| 输出里有半角问号 | 某个符号 cp936 编不出，被替换了 | 本包不会：符号只用 `√ × · →`，金额写「元」。看到了说明是从别处粘进来的字符 |
| 中文文件读成乱码 | 歌词文件不是 UTF-8 | `--a-file` / `--b-file` 要求 UTF-8，转一下再传 |

## 六、参数怎么填

| 参数 | 说明 |
|---|---|
| `--audio-id` | `audio-id` 换来的 ID，或生成音乐时返回的 `audio_id`。它**不是**文件地址 |
| `--audio-url` | 可公网访问的音频地址；本地文件先 `upload` |
| `--start` / `--end` | `vox` 的 `vocal_start` / `vocal_end`，单位秒，只取副歌就填这两个 |
| `--seconds` | `interp` 按秒计费的秒数，也是预算闸门的依据；给太小会被结算补扣 |
| `--budget` | 单位是**点**，默认 6000 = 60 元。超了退 5，一个请求都不发 |
| `--yes` | 写操作必带；缺了退 4，并告诉你要花多少点 |

## 七、退出码

```
0   成功
2   用法错（缺参数、参数非法、路径拼错）
3   自检未通过（doctor 有 × 项）
4   需要 --yes（真实提交前的确认闸门）
5   超预算（--budget 不够，一个请求都没发）
6   调用失败（HTTP 非 200/201，或返回体 code=0）
1   内部错（异常栈，一般是 bug，请附命令与返回）
130 用户中断（Ctrl+C）
```

## 八、还是不通

1. `doctor --json` 把 10 项结果贴出来，`×` 的那一项就是断点。
2. `catalog` 对一遍路径与单价。
3. `cost --seconds 60` 对一遍钱。
4. 带上「命令 + 完整返回体 + `doctor --json`」找技术支持。
