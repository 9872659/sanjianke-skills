# 批量出片与渲染部署

从「渲染一条」到「稳定渲染一万条」，以及本地、单机、云上的选择。

---

## 一、批量的本质：模板 + 数据

批量出片只有一种正确姿势：**画面逻辑写一次，数据换 N 份**。任何一条数据对应一个画面分支的写法都会在第一百条时崩掉。

判断你的模板够不够「批量就绪」，看一个问题：**换一条数据需要改代码吗？** 需要，就还没就绪。

所以先做一件事：把模板里所有会变的东西列出来，全部提升成 props。

| 会变的东西 | 应放的位置 |
|---|---|
| 文案、标题、价格、口播稿 | props（字符串） |
| 品牌主色、Logo、字体 | props 或按客户建的配置文件 |
| 素材路径（图片、视频、配音） | props，值用 `public/` 下的相对路径 |
| 时长 | `calculateMetadata()` 按文案长度算，或 props 直接给 |
| 尺寸、帧率 | 同一模板要出多种规格时用 props + `calculateMetadata()` |

---

## 二、数据组织

### 一份数据一个文件

```text
data/
├─ item-001.json
├─ item-002.json
└─ item-003.json
```

```json
{
  "title": "春季新品上架",
  "price": "¥199",
  "accent": "#ff5722",
  "tags": ["限时", "包邮"],
  "voice": "voice/item-001.mp3"
}
```

为什么不用一个大的数组文件？因为：

- **单条失败不影响其他条**。一条数据格式错了，不需要人工从一千条里挑出来。
- **可以断点续跑**。记录已完成的文件名，重跑时跳过。
- **可以让上游系统直接落文件**。运营在表格里填完，导出一批 JSON 就行。

### 用 CSV 出发（适合非技术同事维护）

给运营一张表比给一堆 JSON 友好得多：

```ts
// scripts/from-csv.ts —— 把 CSV 转成一批 props 文件
import {readFileSync, writeFileSync, mkdirSync} from 'node:fs';
import {parse} from 'csv-parse/sync';

const rows = parse(readFileSync('data/items.csv', 'utf8'), {
  columns: true,
  skip_empty_lines: true,
  bom: true,               // 中文表头必须开，否则第一个字段名会带 BOM 字符
});

mkdirSync('data/items', {recursive: true});

rows.forEach((row, i) => {
  const props = {
    title: row['标题'].trim(),
    price: row['价格'].trim(),
    accent: row['主色'] || '#ff5722',
    tags: (row['标签'] || '').split('/').filter(Boolean),
    voice: row['配音文件'] || '',
  };
  const name = String(i + 1).padStart(4, '0');
  writeFileSync(`data/items/${name}.json`, JSON.stringify(props, null, 2), 'utf8');
});

console.log(`已生成 ${rows.length} 份 props`);
```

**用 `bom: true` 解析 Excel 导出的 CSV**，否则第一个字段名会多出一个不可见字符，取值永远拿到 `undefined`，而且报错信息完全看不出原因。这是中文表格批处理最常见的坑。

---

## 三、用 Node API 批量渲染

CLI 一次只能渲染一条。批量必须走 Node API，这样才有循环、并发控制和错误处理。

### 最小可用版本

```ts
// scripts/batch.ts
import path from 'node:path';
import {readFileSync, readdirSync, mkdirSync, writeFileSync} from 'node:fs';
import {bundle} from '@remotion/bundler';
import {getCompositions, renderMedia} from '@remotion/renderer';

const ENTRY = path.resolve('./src/index.ts');
const DATA_DIR = path.resolve('./data/items');
const OUT_DIR = path.resolve('./out');

async function main() {
  mkdirSync(OUT_DIR, {recursive: true});

  // 1) 打包一次，所有任务复用同一个 serveUrl —— 这是批量提速的关键
  const serveUrl = await bundle({entryPoint: ENTRY});
  const comps = await getCompositions(serveUrl, {
    inputProps: {},
    // 只渲染某一个 Composition，避免打包时把所有 Composition 都求值
    compositionId: 'ProductCard',
  });
  const comp = comps.find((c) => c.id === 'ProductCard');
  if (!comp) throw new Error('找不到 Composition: ProductCard');

  const files = readdirSync(DATA_DIR).filter((f) => f.endsWith('.json'));
  const done: string[] = [];
  const failed: {file: string; reason: string}[] = [];

  for (const [i, file] of files.entries()) {
    const inputProps = JSON.parse(readFileSync(path.join(DATA_DIR, file), 'utf8'));
    const outName = file.replace(/\.json$/, '.mp4');

    try {
      await renderMedia({
        composition: comp,
        serveUrl,                       // 复用打包产物
        codec: 'h264',
        outputLocation: path.join(OUT_DIR, outName),
        inputProps,
        concurrency: 4,
        crf: 18,
        imageFormat: 'jpeg',
        onProgress: ({progress}) => {
          process.stderr.write(`\r[${i + 1}/${files.length}] ${file} ${(progress * 100).toFixed(0)}%`);
        },
      });
      process.stderr.write('\n');
      done.push(outName);
    } catch (err) {
      process.stderr.write('\n');
      // 关键：单条失败必须记下来继续跑，不能整批中断
      failed.push({file, reason: err instanceof Error ? err.message : String(err)});
    }

    // 每渲染一条就落一次清单，进程被杀也能知道跑到哪了
    writeFileSync(
      path.join(OUT_DIR, 'manifest.json'),
      JSON.stringify({done, failed}, null, 2),
      'utf8',
    );
  }

  console.log(`完成 ${done.length} 条，失败 ${failed.length} 条`);
  if (failed.length) console.log(JSON.stringify(failed, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
```

几个刻意的设计：

- **`bundle()` 只调用一次**。每条都重新打包会让整个任务慢好几倍，而且毫无意义——打包产物对同一份代码是相同的。
- **进度写 `stderr`，结果写 `stdout`**。这样 `node script > result.json` 不会把进度日志混进结果里。
- **`manifest.json` 边跑边写**。长任务被系统杀掉或机器重启是常事，有了清单就知道从哪继续。
- **单条 try/catch**。批量任务里一条数据格式错误不应该毁掉其余 999 条。

### 加并发控制

上面的写法是串行的，渲染一条等一条。机器的多核完全没用上。但也不能无脑 `Promise.all` 一千条——那会瞬间占满内存然后全崩。

```ts
// scripts/pool.ts —— 一个极简并发池，避免引入额外依赖
export async function pool<T, R>(
  items: T[],
  limit: number,
  worker: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let cursor = 0;

  const runners = Array.from({length: Math.min(limit, items.length)}, async () => {
    while (true) {
      const index = cursor++;
      if (index >= items.length) return;
      results[index] = await worker(items[index], index);
    }
  });

  await Promise.all(runners);
  return results;
}
```

用法：

```ts
const jobLimit = 2;   // 同时跑 2 条，每条内部 concurrency=4 → 峰值 8 个渲染单元
await pool(files, jobLimit, async (file, i) => { /* 上面的 renderMedia 逻辑 */ });
```

### 「任务并发 × 任务内并发」怎么定

这是批量调优的核心，很多人卡在这里：把两个并发都拉满，然后机器崩。

总并行单元 ≈ `任务并发数 × concurrency 参数`。用这个来估算：

| 机器 | 建议总单元 | 示例组合 |
|---|---|---|
| 4 核 8G | 2–3 | 任务 1 × concurrency 3 |
| 8 核 16G | 4–6 | 任务 2 × concurrency 3，或任务 1 × concurrency 6 |
| 16 核 32G | 8–12 | 任务 4 × concurrency 3 |
| 32 核 64G | 16–24 | 任务 8 × concurrency 3 |

**推荐「多任务 × 小 concurrency」而不是「少任务 × 大 concurrency」。** 原因：

- 单条任务内部的并发是全有全无的——`concurrency` 越大，该任务的峰值内存越高，越容易 OOM。
- 多任务并发时，某条任务结束会让出资源给下一条，整体利用率更平滑。
- 单条任务的日志更干净，出问题时好定位。

**先测单条。** 渲染一条记录耗时和峰值内存，再乘并发数。别靠猜。

### 用 `renderStill()` 先做质检

渲染整片很贵，静帧很便宜。批量任务正式开跑前，先用静帧把画面抽检一遍：

```ts
import {renderStill} from '@remotion/renderer';

await renderStill({
  composition: comp,
  serveUrl,
  output: `out/qa/${file.replace('.json', '.png')}`,
  frame: 30,                 // 挑一个画面信息量最大的帧
  inputProps,
});
```

挑三个帧（入场后、中段、片尾）各出一张，用图片查看器快速翻一遍。文案溢出、字体丢失、素材缺失这类问题在这一步就能发现，比渲染一千条后发现要划算得多。

---

## 四、断点续跑

批量任务最怕的不是失败，是「跑到 800 条时崩了，不知道前 800 条是哪些」。有了清单就能直接续：

```ts
import {existsSync, readFileSync} from 'node:fs';

const manifestPath = path.join(OUT_DIR, 'manifest.json');
const done = new Set<string>(
  existsSync(manifestPath)
    ? (JSON.parse(readFileSync(manifestPath, 'utf8')).done as string[])
    : [],
);

// 只跑还没完成的
const todo = files.filter((f) => !done.has(f.replace(/\.json$/, '.mp4')));
console.log(`跳过已完成 ${done.size} 条，待渲染 ${todo.length} 条`);
```

再加一条保险：**渲染前先删掉可能存在的半截输出文件**。`renderMedia` 遇到同名文件默认会覆盖，但如果上一次是被强杀的，留下一个 0 字节文件会让下游的转码、上传步骤误判成功。

```ts
const outPath = path.join(OUT_DIR, outName);
if (existsSync(outPath)) rmSync(outPath);   // 由已完成清单决定要不要跑，跑到这里就该重来
```

---

## 五、输出图序列再统一编码

有些场景不适合直接出 MP4：

- 需要在编码前做统一处理（加水印、拼接、调色）。
- 多台机器分片渲染，最后合并。
- 要复用同一批帧出多种规格（不同码率、不同容器）。

```bash
# 出 PNG 序列（无损，体积大）
npx remotion render ProductCard out/frames --sequence --image-format=png

# 出 JPEG 序列（快，小）
npx remotion render ProductCard out/frames --sequence --image-format=jpeg --jpeg-quality=95
```

然后用自带的 FFmpeg 重新编码：

```bash
npx remotion ffmpeg -framerate 30 -i out/frames/frame-%04d.png \
  -c:v libx264 -pix_fmt yuv420p -crf 18 out/final.mp4
```

`%04d` 是零填充的帧号占位符，位数要跟实际文件名对齐（`--image-sequence-pattern` 可以自定义命名规则）。

**磁盘预警**：1080p PNG 一帧大约 1.5–3 MB。30fps 意味着**每秒 45–90 MB**。一条 30 秒的片子就是 1.5–2.5 GB。出图序列前先算好空间，跑完立刻转码并清理，不要让它堆在磁盘上。

---

## 六、部署方案选型

| 方案 | 适合 | 不适合 | 代价 |
|---|---|---|---|
| 本地 / 开发机 | 开发调试、低频出片（每天几十条） | 大批量、需要 7×24 定时 | 机器被占满时没法干别的 |
| 单台服务器（自建） | 每天数百到数千条、数据不能出内网 | 突发性万级任务 | 需要自己管进程、日志、清理 |
| Lambda（云函数） | 突发大批量、按需付费 | 数据合规要求不出内网 | 需要 AWS 账号，冷启动与打包体积有约束 |
| Cloud Run | 已有 GCP、想用容器化方案 | 追求最低单价 | 需要 GCP 项目与镜像仓库 |
| 客户端渲染 | 用户在自己浏览器里导出 | 服务端批处理 | 受用户机器性能限制 |

### 单台服务器的工程化

真正上生产要补的东西，按重要性排序：

1. **进程守护**：用 systemd / pm2 / supervisor 托管批量脚本，崩溃自动重启。
2. **日志落盘 + 轮转**：渲染日志量很大，一定要限制单文件大小并定期清理。
3. **失败的独立告警**：清单里的 `failed` 数组非空就发通知，别让它悄悄躺着。
4. **输出清理策略**：产物上传到对象存储后删本地，或按天数淘汰。磁盘满是最常见的生产事故。
5. **资源隔离**：渲染是 CPU 与内存密集型，别跟数据库、Web 服务放同一台机器。
6. **渲染前检查磁盘余量**：至少留出「单条产物体积 × 并发数 × 2」的空间。

### 云渲染：Lambda 与 Cloud Run

两者的用法接近：把代码打包上传，云上一次性拉起几百个实例并行渲染，最后把结果拼起来。单条十分钟的片子能压到几十秒。

```bash
# Lambda 路线（概念流程，具体子命令以上游当前版本为准）
npx remotion lambda policies validate     # 校验 IAM 权限
npx remotion lambda functions deploy      # 部署渲染函数
npx remotion lambda sites create          # 上传打包产物到 S3

npx remotion lambda render <serve-url> ProductCard \
  --props=./data/item-001.json
```

上云前必须算清楚的账：

- **云算力费用**：渲染实例 + 对象存储 + 出网流量，三者都可能超出预期。
- **数据合规**：素材和文案会离开你的内网。涉及用户隐私或商业机密时先过合规。
- **区域可用性**：云渲染不是所有区域都支持，选离素材存储近的区域能省大量传输时间。
- **打包体积**：渲染函数有体积上限，`node_modules` 里塞了 FFmpeg 二进制和大字体包很容易超。用 webpack 把渲染逻辑单独打一个轻量入口，不要把所有依赖都带上。

### 定时任务

CI 或系统计划任务里跑批量，关键是**缓存依赖 + 幂等**：

```yaml
# .github/workflows/daily-video.yml
name: 每日视频
on:
  schedule:
    - cron: '0 22 * * *'    # UTC 22:00 = 北京时间次日 06:00
  workflow_dispatch:

jobs:
  render:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci
      - run: node scripts/batch.js
        env:
          # 公司许可必须配置，见下方许可段落
          REMOTION_LICENSE_KEY: ${{ secrets.REMOTION_LICENSE_KEY }}
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: videos
          path: out/*.mp4
          retention-days: 7
```

`if: always()` 让部分失败时也能拿到已成功的产物，对排查很有用。

---

## 七、许可：批量场景必须额外确认的三件事

批量渲染是许可条款最敏感的地方，动手前把这三条弄清楚。

### 1. 你的批量脚本算不算 automation

**算。** 官方明确把「你自己的代码程序化调用渲染入口」定义为 automation，被点名的入口包括 `renderMedia()`、`renderStill()`、`renderFrames()`、各类云渲染封装，以及 `npx remotion render` / `npx remotion still` 命令行。

也就是说，**只要你的脚本用了上面任意一个，就不是「手动低频」了**，别再拿这个理由安慰自己。

### 2. 你需要买哪一档

| 你的情况 | 结论 |
|---|---|
| 个人，无论自用还是商用 | Free License，批量也不需要买 Render |
| 组织 ≤ 3 人 | Free License，批量也不需要买 Render |
| 非营利组织 | Free License |
| 组织 ≥ 4 人，只是给自己做视频、没搭自动化 | Creators 口径，按席位买 |
| 组织 ≥ 4 人，有自动化管线 / 做视频产品 / 嵌入 Player | Automators 口径，按渲染次数买（约 $0.01/次，$100/月起） |

**注意两层判断是独立的**：人数决定「要不要买」，场景决定「买哪种」。一个 20 人的公司即使只是给自己做片子，也逃不掉——只是可以走 Creators 口径按席位算。反过来，个人做自动化工具依然免费。

一次 Render 的定义是「成功产出一个视频、音频、GIF、PDF 或静图」。**Studio 和 Player 里的预览不算 Render。** 所以你的批量脚本跑了 1000 条，就是 1000 次 Render。

### 3. telemetry 与 `licenseKey`

自 5.0 起，**Automators 与 Enterprise 档强制上报**：必须从许可平台取 `licenseKey`，配置到渲染里，每次渲染发一个匿名事件。

- 上报内容：触发渲染机器的 IP、是否生产环境、是视频还是静图。
- **不采集**任何画面内容、素材、元数据或用户数据。
- 客户端渲染（`renderMediaOnWeb()` 那条路）对**所有人**都强制上报，不论许可档位。
- 免费档与 Creators 档的服务端渲染属自愿：不配 `licenseKey` 就不上报。
- 免费档可以传 `"free-license"` 作为 `licenseKey` 值，用来声明自己的免费资格并消掉控制台警告。
- **telemetry 不会限流、阻断或让渲染失败。** 即使上报请求本身失败，渲染照样完成。
- 如果因为防火墙或企业策略无法上报，需要走 Enterprise 定制协议，并提供可核验的月度渲染活动报告。

配置方式（值从环境变量来，不要写进代码）：

```ts
await renderMedia({
  composition: comp,
  serveUrl,
  codec: 'h264',
  outputLocation: outPath,
  inputProps,
  licenseKey: process.env.REMOTION_LICENSE_KEY,   // 公司档必须；免费档可传 'free-license'
});
```

### 4. 商业使用的红线

- **允许**：用户基于你提供的模板生成自己的视频；用 LLM 生成 Remotion 代码再渲染；让用户编辑由你服务生成的代码。
- **不允许**：让用户把**自己的** Remotion 工程上传到你的服务器渲染。这条是硬线，做「通用渲染服务」时会直接踩到。
- **代理与外包**：客户只拿成片文件、不接触工程代码 → 客户人数不计入门槛；客户拥有或继续开发该工程，或你引入外部工作室/自由职业者协作同一工程 → **双方人数合并计算**。
- **编码器专利不在许可涵盖范围内**。H.264/HEVC/AAC 的专利授权是独立问题，是否需要额外付费取决于使用方式与司法辖区，责任在你自己。

价格与条款会变动。最终依据永远是官方许可页面与仓库根目录的 `LICENSE.md`，本 Skill 只做转述。

---

## 八、批量任务上线前的自检

- [ ] 换数据不需要改代码（模板已完全参数化）。
- [ ] props 全部可 JSON 序列化。
- [ ] 用 `renderStill()` 抽帧质检过，画面没有溢出、缺字、缺素材。
- [ ] `bundle()` 在循环外只调用一次。
- [ ] 「任务并发 × concurrency」按机器内存估算过，不是两个都拉满。
- [ ] 单条失败不会中断整批，失败清单被记录下来。
- [ ] `manifest.json` 边跑边写，支持断点续跑。
- [ ] 渲染前会清理同名残留文件，避免 0 字节产物被当成成功。
- [ ] 磁盘余量、日志轮转、输出清理策略都已配置。
- [ ] 许可档位按人数与场景判定完毕；公司档 automation 已配 `licenseKey`。
- [ ] 云渲染的算力与存储账单由自己的账号承担，并配置了生命周期清理规则。
- [ ] 已评估编码器专利授权的适用性。
