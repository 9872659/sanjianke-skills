# surya 命令、参数与后端速查

> 以 Surya 2 的 README 与代码为准整理。项目迭代快，**参数名与默认值请以实际安装版本的
> `surya_ocr --help` 和官方文档为最终依据**，本页只作为速查。

## 四个命令行入口

| 命令 | 干什么 | 需要 VLM 后端吗 |
|---|---|---|
| `surya_ocr` | 整页 OCR，输出 blocks（文字、html、坐标、置信度） | 需要 |
| `surya_layout` | 版面分析 + 阅读顺序 | 需要 |
| `surya_table` | 表格识别（行列、单元格、可选 HTML） | 需要 |
| `surya_detect` | 文字行检测，只出 bbox | **不需要**，纯 torch |
| `surya_gui` | Streamlit 交互界面（装了 streamlit / pdftext 才有） | 需要 |

## 通用参数

| 参数 | 说明 |
|---|---|
| `DATA_PATH` | 位置参数。单张图片、单个 PDF，或装着图片/PDF 的目录 |
| `--output_dir` | 结果目录，默认固定位置，多次运行会互相覆盖 |
| `--images` | 额外输出每页的图像与标注可视化 |
| `--page_range` | 只处理指定页。写法：单页 `3`、列表 `0,5,10`、区间 `5-10`、组合 `0,5-10,20` |
| `--keep_server` | 命令结束后保留推理服务，后续命令直接附着，不重新加载模型。**所有命令都支持** |

`surya_table` 独有：

| 参数 | 说明 |
|---|---|
| `--skip_table_detection` | 跳过表格检测，直接把整张图当成表格处理。图已经裁到只剩表格时用 |

## 推理后端

版面、OCR、表格识别共用一个 VLM，由 vllm（GPU）或 llama.cpp（CPU / Apple Silicon）提供。
`SuryaInferenceManager` 会在首次使用时自动拉起；也可以指向已在跑的服务。

```bash
export SURYA_INFERENCE_BACKEND=vllm                        # vllm | llamacpp | 不设=自动
export SURYA_INFERENCE_URL=http://localhost:8000/v1        # 附着到已有的 OpenAI 兼容服务
export SURYA_INFERENCE_PARALLEL=8                          # 客户端并发
export SURYA_INFERENCE_KEEP_ALIVE=1                        # 退出后保留服务
export SURYA_GUIDED_LAYOUT=1                               # true=JSON Schema 约束版面解码
export DETECTOR_BATCH_SIZE=8                               # 检测模型的显存/吞吐
```

### 后端前置条件

- **NVIDIA GPU**：Docker + NVIDIA Container Toolkit（vllm 在容器里跑）
- **CPU / Apple Silicon**：`llama-server` 二进制。macOS 用 `brew install llama.cpp`；
  其他平台从 llama.cpp 的 Releases 取

### 服务生命周期

默认每条命令启动时拉起服务、退出时关掉，等于每次都要付启动（GPU 上还有模型加载）成本。
连着跑多条命令时：

```bash
surya_ocr    DATA_PATH --keep_server   # 拉起并保留
surya_layout DATA_PATH                 # 附着，不重启
surya_table  DATA_PATH                 # 继续附着
```

收工记得停掉：`docker stop` 掉 `surya-vllm-*` 容器，或杀掉 `llama-server` 进程。

## settings 与环境变量覆盖

`surya/settings.py` 里集中了全部可调项，任何一项都能用同名环境变量覆盖。README 点名的
调优旋钮：

- **DPI**：影响吞吐和精度。官方举例从 192 降到 96 换吞吐
- **vllm** 侧：`--max-num-seqs` / `--max-num-batched-tokens`
- **llama.cpp** 侧：`SURYA_INFERENCE_PARALLEL` 要和 `llama-server` 的 `--parallel` 对齐
- **检测阈值**：`DETECTOR_TEXT_THRESHOLD`（判定为文字）与 `DETECTOR_BLANK_THRESHOLD`
  （判定为行间空白）。后者必须小于前者，都是 0~1。如果看到该分的框被粘在一起就抬高，
  看到淡淡的框没检出来就降低

## Python API（v2）

```python
from surya.inference import SuryaInferenceManager
from surya.layout import LayoutPredictor
from surya.recognition import RecognitionPredictor
from surya.table_rec import TableRecPredictor

manager = SuryaInferenceManager()   # 三个 Predictor 共用这一个实例
```

- `RecognitionPredictor(manager)(images)` → 整页 OCR
- `RecognitionPredictor(manager)(images, layout_results)` → 块级 OCR
- `LayoutPredictor(manager)(images)` → 版面
- `TableRecPredictor(manager)(images)` → 简单模式；`predict_full(images)` → 含 HTML 的完整模式

v1 → v2 的迁移要点：`FoundationPredictor` 被 `SuryaInferenceManager` 取代。
