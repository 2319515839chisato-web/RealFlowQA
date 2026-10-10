# RealFlowQA

RealFlowQA 是一个面向流程图结构解析与问答的数据集合。当前目录包含流程图图片、Gold-StructFlow、Auto-StructFlow、问题与参考答案、结构生成代码，以及三种模型答题提示词。

## 数据规模

| 内容 | 数量 |
|---|---:|
| 流程图图片 | 82 |
| Gold-StructFlow | 82 |
| Auto-StructFlow | 82 |
| 问题与参考答案 | 527 |

流程图编号范围为 `chart_001` 至 `chart_082`。图片、Gold-StructFlow、Auto-StructFlow 和问题表中的 `chart_id` 一一对应。

527道问题包含四种题型：

| `question_type` | 数量 |
|---|---:|
| `responsibility` | 154 |
| `next_step` | 119 |
| `conditional_branch` | 126 |
| `path_trace` | 128 |

每张流程图对应5至8道问题。

## 目录结构

```text
RealFlowQA/
├── data/
│   ├── image/
│   │   ├── chart_001.jpg
│   │   └── ...
│   ├── gold_structFlow/
│   │   ├── chart_001_structure.json
│   │   └── ...
│   ├── auto_structflow/
│   │   ├── chart_001_structure.json
│   │   └── ...
│   └── questions.xlsx
├── prompts/
│   └── 模型回答提示词.txt
└── src/
    ├── clients.py
    ├── prompts.py
    └── run_structure.py
```

## 问题与答案

`data/questions.xlsx` 的工作表名称为 `questions`，包含以下字段：

| 字段 | 含义 |
|---|---|
| `chart_id` | 流程图编号 |
| `question_id` | 当前流程图内的问题编号 |
| `question_type` | 问题类型 |
| `question_text` | 问题文本 |
| `gold_answer_text` | 参考答案文本 |

当前表格中五个字段均无空值，`chart_id + question_id` 组合无重复。

四种题型分别用于考查：

- `responsibility`：流程节点或动作对应的责任主体。
- `next_step`：给定节点完成后的后续节点或承接主体。
- `conditional_branch`：指定条件下进入的节点或流程分支。
- `path_trace`：两个节点之间或指定流程范围内的执行路径。

## StructFlow 格式

Gold-StructFlow 与 Auto-StructFlow 均为 JSON 文件，顶层包含以下字段：

| 字段 | 含义 |
|---|---|
| `chart_id` | 流程图编号 |
| `title` | 流程图标题 |
| `lanes` | 泳道或责任区域 |
| `nodes` | 流程执行节点 |
| `edges` | 节点之间的有向连接 |

### `lanes`

每个泳道包含：

- `lane_id`
- `name`
- `description`

### `nodes`

每个节点包含：

- `node_id`
- `text`
- `full_label`
- `lane_id`
- `responsible`

### `edges`

每条有向边包含：

- `edge_id`
- `from`
- `to`
- `condition`
- `edge_type`
- `description`

`from` 和 `to` 使用节点的 `node_id`。结构生成提示词将 `edge_type` 定义为普通流程边 `normal`、条件分支边 `condition` 或循环与回退边 `loop`。

当前 Gold-StructFlow 共包含408个泳道、1354个节点和1459条边；Auto-StructFlow 共包含407个泳道、1337个节点和1417条边。

## 图片

`data/image/` 中包含82张 JPEG 图片，文件名使用 `chart_xxx.jpg` 格式，与对应结构文件及问题表中的 `chart_id` 保持一致。

## 提示词

`prompts/模型回答提示词.txt` 包含三种答题设置所使用的提示词：

1. 直接读取原始流程图回答问题；
2. 结合原始流程图与 Auto-StructFlow 回答问题；
3. 结合原始流程图与 Gold-StructFlow 回答问题。

`src/prompts.py` 包含流程图图片到 StructFlow JSON 的结构生成提示词，同时包含结构增强问答提示词模板。

## 结构生成代码

`src/run_structure.py` 用于按 `chart_id` 批量读取流程图图片、调用视觉语言模型并将返回结果规范化为 StructFlow JSON。最终保留的顶层字段为 `chart_id`、`title`、`lanes`、`nodes` 和 `edges`。

`src/clients.py` 提供 OpenAI 兼容接口的模型调用封装，并执行以下图像预处理：

- 将图片转换为 RGB；
- 将最长边限制为1600像素；
- 使用 LANCZOS 方法缩放；
- 编码为质量参数85的 JPEG；
- 转换为 Base64 图像数据。

当前结构生成代码中的主要调用参数为：

| 参数 | 当前值 |
|---|---|
| 模型 | `gpt-5.4` |（具体调用的模型请根据需求自行切换）
| `temperature` | `0.0` |
| `max_tokens` | `1024` |
| 外层最大重试次数 | `5` |
| 两次请求之间的等待时间 | `5` 秒 |
| 客户端最大重试次数 | `2` |
| 连接超时 | `60` 秒 |
| 读取、写入及总体超时 | `240` 秒 |

代码使用的第三方 Python 包包括：

- `pandas`
- `openai`
- `httpx`
- `Pillow`

