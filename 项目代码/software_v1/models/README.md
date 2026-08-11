模型权重、数据集和缓存不提交到仓库。正式联调前必须由部署环境填写 `configs/model_manifest.json` 中的检查点 SHA-256、配置哈希、数据哈希、真实评估指标、运行时版本和对应 Git commit。

部署路径由 `MODEL_ROOT` 约束，服务只接受 `MODEL_CONFIG_PATH`、`MODEL_CHECKPOINT_PATH` 和 `MODEL_TOKENIZER_PATH` 等受控配置，不接受请求传入模型路径。清单标签顺序必须与模型契约一致；缺失真实哈希或指标时，系统应保持未就绪，不得生成正式模型结论。

Docker模板将宿主机`MODEL_HOST_DIR`只读挂载到`/app/models`。默认约定如下：

```text
/app/models/
├── checkpoints/model.pt
├── albert-base-v2/
└── tokenizer/
```

`albert-base-v2/`必须是可由`AlbertModel.from_pretrained()`离线读取的完整基础模型目录。融合检查点会覆盖其参数，但程序仍需先从该目录构造ALBERT网络结构。`tokenizer/`必须包含与训练一致的Tokenizer文件。

检查点必须是完整`CascadeDetector`状态字典，且同时包含`semantic.encoder.*`、`behavior.gru.*`和`fusion.*`参数。只包含ALBERT、只包含GRU或包含LSTM参数的文件都会被加载器拒绝。
