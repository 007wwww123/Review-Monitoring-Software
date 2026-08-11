# 系统架构

## 模型边界

系统只接受完整的ALBERT-GRU门控融合检查点。加载器会检查`semantic.encoder.*`、`behavior.gru.*`和`fusion.*`参数；LSTM或单阶段检查点会被拒绝。

最终真假概率来自`softmax(fusion.authenticity_logits)`，默认阈值为0.5，部署值由`model_manifest.json`记录。`allow_type_override`固定为`false`，语义和行为细分类不能覆盖最终真假。

历史不足时仍执行GRU和融合，但`behavior_available=0`会使门控退化为语义主导，行为类别输出`insufficient_evidence`。

## 应用数据流

1. 用户登录后提交评论原始字段和可选原始历史事件。
2. 后端使用哈希后的用户标识从MySQL查询目标时间之前的历史。
3. 服务器合并、去重并截取最近30条历史。
4. 统一特征构建器生成GRU序列，ALBERT同时编码文本。
5. 门控融合头输出最终真假，辅助头输出相对匹配度。
6. 结果、模型版本、解释快照和操作记录写入MySQL。
7. 批量请求先写入队列，独立Worker逐条处理并更新进度。

## 运行时

FastAPI使用lifespan加载一次模型并保存到`app.state`。批量Worker是独立进程，也只在进程启动时加载一次。模型身份由manifest和SHA-256决定，网页不支持热切换。

后端进程启动时创建SQLAlchemy Engine；每个请求创建并关闭Session；进程退出时释放Engine。
