# 功能追踪矩阵

| 功能 | 后端/模型实现 | 前端或接口 | 验证状态 |
| --- | --- | --- | --- |
| ALBERT-GRU门控融合 | `model_core/spam_cascade/modeling.py` | 单条与批量检测 | 本地结构测试；GPU前向待云端核实 |
| 统一行为特征 | `BehaviorFeatureBuilder` | 原始历史事件请求 | 训练/线上一致性测试已编写 |
| 完整时间历史查询 | `ReviewEvent.review_time`与仓储查询 | `date`带时区 | ORM/API测试；MySQL迁移待部署核实 |
| 最终融合决策 | `DecisionRouter.finalize` | Explanation JSON v2 | 路由单测通过 |
| 单例模型加载 | FastAPI lifespan与Worker启动器 | 健康接口 | 无权重环境下仅静态验证 |
| 批量异步任务 | `DetectionTaskItem`与Worker | 任务状态轮询 | SQLite服务测试通过 |
| 真实模型评估 | `AdminService.evaluate` | 评估接口 | 代码完成；GPU测试待云端核实 |
| 登录与权限 | JWT依赖与管理员依赖 | 登录、检测、模型、评估接口 | API测试通过 |
| Docker部署 | `deploy/` | Nginx入口 | 模板完成；目标服务器待核实 |
