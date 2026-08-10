# 项目协作说明

##禁区
- 未明确要求时，不要批量升级依赖、修改数据库迁移历史、删除本地运行数据。
##交付格式
- 说明改了什么，跑了什么验证，还有什么风险。

## 1. 项目定位

本仓库开发“基于语义—时序门控融合的虚假评论智能检测系统”。目标形态是浏览器/服务器（B/S）架构的审核与风险分析平台，模型在服务器本地运行，不依赖第三方在线 AI API。

当前版本标记为 `V1.0.0（开发中）`。截至本文件建立时，可验证的实现集中在模型核心；FastAPI 后端、Vue 前端、数据库、部署和报告等应用层仍是空目录或空文件骨架，不能当作已有功能。

## 2. 仓库结构与当前状态

- `项目代码/software_v1/`：软件主目录。
- `项目代码/software_v1/model_core/`：应用准备复用的模型核心副本，包含 `spam_cascade` 包、依赖清单和单元测试。
- `项目代码/lstm_variant/`：冻结的科研训练基线，包含训练入口 `train.py`、最终评估入口 `evaluate.py`、配置、模型包和测试。应用开发不要直接修改此目录中的模型结构、分类头或标签顺序。
- `software_v1/model_core/spam_cascade/` 与 `lstm_variant/spam_cascade/` 当前逐文件内容一致；两处测试也一致。若确需修改模型核心，必须说明同步策略并运行两处相关测试，避免副本漂移。
- `software_v1/configs/base.json`：当前模型基础配置。
- `software_v1/backend/`：只有目录和空文件骨架，尚无可运行 FastAPI 应用。
- `software_v1/frontend/`：只有目录和空文件骨架，`package.json` 与 `src/main.ts` 为空，尚无可运行 Vue 应用。
- `software_v1/configs/app.yaml`、`configs/model_manifest.json`、`models/README.md`、`THIRD_PARTY_NOTICES.md` 当前为空。
- `software_v1/deploy/`、`docs/`、`runtime/`、`scripts/` 当前没有已提交的实现文件。

README 中提到的 FastAPI、Vue 3、TypeScript、Element Plus、ECharts、MySQL 8、SQLAlchemy、Alembic、Docker、Nginx 等均属于规划技术栈；在对应依赖和代码落地前，不要描述为已实现。

## 3. 模型流程与关键约束

模型采用三部分流程：

1. ALBERT 处理评论文本，执行真实/虚假判断，并输出语义相对匹配度。
2. LSTM 处理用户按时间排序的行为序列。每个时间步是 10 维数值行为特征，不是文本 Token。
3. 语义与行为表示经过门控融合，生成最终真实性、语义类型、行为类型和处置建议。

所有评论都必须进入语义、行为和融合流程。`DecisionRouter.route()` 当前固定返回 `run_fusion`，不要依据旧的“提前退出”命名或阈值擅自跳过融合。历史不足时，通过 `behavior_available=0` 掩码退化为语义主导，并输出 `insufficient_evidence`；不得将“历史不足”解释成“行为正常”。

必须保持以下标签顺序，因为配置校验、张量维度、训练与推理契约都依赖它：

- 语义标签：`real`、`misleading`、`exaggerated`、`advertising`。
- 行为标签：`normal`、`review_manipulation`、`crowdturfing`、`bot_like`、`insufficient_evidence`。
- 可学习的异常行为细类只有前三种异常类型；`insufficient_evidence` 是证据状态，不是可学习类别。

解释输出时遵守以下边界：

- 门控权重只是融合权重摘要，不是因果归因。
- 细分类分数在没有独立标签监督和校准时，只能称为相对匹配度，不能称为确定类别。
- 当前行为二分类使用原始评论真假标签作为代理任务：`label=1 -> normal=0`，`label=-1 -> abnormal=1`，并非独立人工标注的异常行为真值。
- `risk_source` 是规则派生结果，只能作为输出，不能作为模型输入。
- 检测结果是辅助审核建议，不替代人工事实认定。

## 4. 数据契约

训练/评估输入为 TSV，至少包含：

```text
user_id, prod_id, rating, label, date, text
```

- `review_id` 可选；缺失时加载器按文件行生成。若提供，必须非空且在单个 TSV 内唯一。
- `date` 必须能被 Pandas 严格解析。
- 原始二分类标签只支持 `1` 和 `-1`。
- 可选监督字段为 `semantic_type` 和 `behavior_type`。
- 行为特征必须按 `user_id`、`date`、`review_id` 稳定排序，只可读取目标事件及其过去事件，严禁使用未来事件或标签构造特征。
- 当前行为特征维度为 10，历史长度配置为最少 1、最多 30；修改时同步检查配置、特征构造器和模型输入维度。
- 无标签线上推理请求与带 `label` 的训练数据结构尚未由后端适配层实现，开发时应明确分离两种契约。

## 5. 模型配置基线

`software_v1/configs/base.json` 当前可验证的主要配置如下：

- 预训练模型标识：`albert/albert-base-v2`。
- 最大文本长度：256。
- 行为输入维度：10；LSTM 隐层：128；层数：1。
- 融合隐层：256。
- 最少/最多历史长度：1/30。

配置中的阈值字段仍被保留，但当前路由策略是强制融合。不要仅凭字段名称恢复提前退出逻辑。

## 6. 开发与验证命令

模型核心依赖记录在 `项目代码/software_v1/model_core/requirements.txt`，Python 依赖范围包括 PyTorch、Transformers、SentencePiece、Protobuf、Pandas、NumPy、scikit-learn 和 tqdm。仓库未声明 Python 解释器版本，因此具体 Python/CUDA 兼容性需要在目标环境自行核实。

在 PowerShell 中运行模型核心测试：

```powershell
Set-Location '项目代码/software_v1/model_core'
python -m unittest discover -s tests -v
```

冻结训练基线的测试：

```powershell
Set-Location '项目代码/lstm_variant'
python -m unittest discover -s tests -v
```

训练入口位于 `项目代码/lstm_variant/train.py`，阶段参数为 `semantic`、`behavior` 或 `fusion`。具体参数以 `python train.py --help` 和该目录 README 为准。融合训练依赖已训练的语义与行为检查点。

最终评估入口为 `项目代码/lstm_variant/evaluate.py`，只应在训练方案、阈值和超参数确定后对封存测试集执行。测试集不得参与训练、模型选择、阈值选择或调参。

## 7. 修改原则

- 先检查实际文件内容，再更新状态说明；不要根据规划目录推断功能已经完成。
- 应用层通过 `software_v1/backend/app/ml/adapter.py` 适配模型核心。该文件目前为空，实施时应把训练数据结构与线上推理请求明确隔离。
- 不要提交模型权重、数据集、Hugging Face 缓存、数据库密码、密钥、令牌、上传文件、运行日志或生成报告。
- 模型文件路径只能来自受控配置，不允许由请求直接指定任意服务器路径。
- 密码、密钥和令牌只能通过环境变量注入；用户标识应做匿名化处理。
- 修改数据处理时，优先补充防止未来信息泄漏、重复 `review_id`、缺失行为历史和标签顺序变化的测试。
- 修改模型输出、标签、配置或适配器时，要同时检查训练、推理、解释、API Schema、TypeScript 类型和导出报告的契约；后四项尚未实现时，应在实现中保持同一套定义。

## 8. 尚未确认或尚未实现

- 仓库当前没有 Git 提交历史，无法从版本记录核实设计演进。
- 模型权重、数据集、实际训练指标、校准结果、运行硬件和部署环境均不在仓库中，无法确认。
- `model_manifest.json` 尚未填写，正式部署前应记录检查点 SHA-256、标签顺序、Tokenizer、数据哈希、指标快照、依赖/CUDA 版本和对应 Git 提交。
- 后端 REST API、七个主页面、登录、数据库迁移、批量任务、报告、Docker Compose 和软著操作说明均为规划内容，当前没有可验证实现。

以上未知项不得猜测；需要使用相关信息时，应先向项目负责人确认或通过权威文件、实际代码和可复现实验核实。
