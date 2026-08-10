# 语义—行为门控融合虚假评论检测模型

本项目实现三级检测流程：

1. ALBERT对评论文本执行真实性判断，并生成四维语义相对匹配度；
2. LSTM对用户时序行为执行正常/异常二分类，并在异常条件下生成三种行为类型匹配度；
3. 两路表示投影到统一的256维空间，通过缺失感知向量门控完成融合。

## LSTM来源说明

行为分支接收的是每个时间步的10维数值型行为特征，而不是文本Token。因此本变体使用
PyTorch官方`torch.nn.LSTM`构建与原GRU分支等价的时序编码器，并在本项目行为数据上从头训练。
Hugging Face继续用于下载ALBERT文本预训练权重；Hub上的通用文本LSTM检查点与本项目10维行为输入不兼容，不能直接替换。

训练完成后，可以把`behavior_lstm_best.pt`上传到Hugging Face Hub，之后再把它作为本项目专用的LSTM行为检查点下载和复用。

## 层级输出

语义相对匹配度由真实性概率与条件类型概率派生：

```text
[P(real), P(fake)P(misleading|fake), P(fake)P(exaggerated|fake), P(fake)P(advertising|fake)]
```

行为相对匹配度由正常性概率、条件异常类型概率和行为可用掩码派生：

```text
[mP(normal),
 mP(abnormal)P(manipulation|abnormal),
 mP(abnormal)P(crowdturfing|abnormal),
 mP(abnormal)P(bot-like|abnormal),
 1-m]
```

`insufficient_evidence`是行为标注状态，不作为可学习行为类别。门控可用性`m`只由历史长度决定，不能由行为标签决定，避免把训练标签泄漏给融合门。

## 数据字段

TSV至少包含：

```text
user_id, prod_id, rating, label, date, text
```

`review_id`可选；若TSV中没有该列，加载器会按文件内行号自动生成。`user_id`仍然是构建真实时序历史所必需的字段。

LSTM正常/异常二分类直接使用原始`label`：

```text
label=1  -> normal=0
label=-1 -> abnormal=1
```

因此只有原始二分类标签的数据也能直接训练LSTM。训练细粒度辅助头时才额外需要：

```text
semantic_type, behavior_type
```

缺少`behavior_type`时，三种异常行为类型辅助损失会自动关闭，但LSTM二分类训练不受影响。此时模型仍保留行为类型匹配度输出接口，但这些细类分数没有经过监督校准，不能直接作为可靠类别结论。

`risk_source`只能作为最终派生结果，不能作为模型输入。行为特征严格按用户和时间排序，目标样本不能读取未来事件。

## 第一层ALBERT训练

```bash
python -u train.py \
  --stage semantic \
  --data /path/to/train.tsv \
  --val-data /path/to/val.tsv \
  --config configs/base.json \
  --output checkpoints/semantic \
  --epochs 5 \
  --batch-size 16 \
  --gradient-accumulation-steps 2 \
  --learning-rate 2e-5
```

现有E0权重仍可加载。模型继续保留四行`semantic_head`参数，但推理时只使用后三行计算虚假条件类型概率。

## 第二层LSTM训练

```bash
python -u train.py \
  --stage behavior \
  --data /path/to/train.tsv \
  --val-data /path/to/val.tsv \
  --config configs/base.json \
  --output checkpoints/behavior-binary \
  --epochs 20 \
  --batch-size 512 \
  --learning-rate 1e-3 \
  --weight-decay 1e-4 \
  --early-stopping-patience 3 \
  --class-weight-exponent 0.5 \
  --behavior-type-loss-weight 0.3
```

行为主任务标签：

```text
原始label=1  -> normal=0
原始label=-1 -> abnormal=1
历史不足     -> mask，不计算行为损失
```

最佳模型依据异常类F1与PR-AUC的平均值选择，而不是Accuracy。

## 门控融合训练

完成ALBERT和LSTM训练后执行：

```bash
python -u train.py \
  --stage fusion \
  --data /path/to/train.tsv \
  --val-data /path/to/val.tsv \
  --config configs/base.json \
  --semantic-checkpoint checkpoints/semantic/semantic_albert_best.pt \
  --behavior-checkpoint checkpoints/behavior-binary/behavior_lstm_best.pt \
  --output checkpoints/fusion \
  --epochs 5 \
  --batch-size 16 \
  --gradient-accumulation-steps 2 \
  --learning-rate 1e-4 \
  --semantic-learning-rate 1e-5 \
  --class-weight-exponent 0.5 \
  --behavior-type-loss-weight 0.3 \
  --freeze-encoders-epochs 1
```

融合训练会分别为真实性、条件语义类型、行为二分类和条件行为类型计算软化类别权重，并在每轮验证后打印三条分类报告。行为历史不足时，融合门自动强制语义分支占主导，不会把缺失行为误判为正常行为。

## 检查点

每个正式训练阶段输出：

```text
best.pt       完整最佳训练状态
latest.pt     最近训练状态，用于断点恢复
epoch_*.pt    可选的逐轮检查点
*_best.pt     部署用纯模型权重
*_last.pt     最后一轮纯模型权重
history.jsonl 每轮训练与验证指标
```

`test.tsv`不得参与训练、阈值选择或参数调整，只在全部方案确定后进行一次最终内部测试。
