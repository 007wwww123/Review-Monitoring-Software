模型权重、数据集和缓存不提交到仓库。正式联调前必须由部署环境填写 `configs/model_manifest.json` 中的检查点 SHA-256、配置哈希、数据哈希、真实评估指标、运行时版本和对应 Git commit。

部署路径由 `MODEL_ROOT` 约束，服务只接受 `MODEL_CONFIG_PATH`、`MODEL_CHECKPOINT_PATH` 和 `MODEL_TOKENIZER_PATH` 等受控配置，不接受请求传入模型路径。清单标签顺序必须与模型契约一致；缺失真实哈希或指标时，系统应保持未就绪，不得生成正式模型结论。
