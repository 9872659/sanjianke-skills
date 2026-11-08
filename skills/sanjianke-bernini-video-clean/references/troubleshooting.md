# 排错：Bernini视频去水印和字幕

## 先跑 `info`

免费，只读 GET，能排掉一半问题（Key 通不通、应用在不在架）。

## 常见报错

### 「缺必填参数 nXXX_xxx」

用 `params` 看全表，然后：
```bash
python3 scripts/run.py run --set nXXX_xxx=值 --yes
```

### 「上传失败」

`POST /api/v1/gpu/assets` 的字段是 `file` + `media_type`（image/video/audio）+ `purpose`。
本地文件路径要对，单个文件别太大。

### 轮询一直 pending

工作流要排队。默认 `--limit 1800`（30 分钟）。超时会给你 `run_order_id`，
**用同一个 id 再查，不要重提**（重提会再扣一次）。

### 「预计 N 点超过 --budget M 点」

闸门在工作。调大 `--budget` 或减少 `--count`。

## 价格

**225.0 点/次（¥2.25）**，上游 ¥1.5。失败按平台规则处理。
