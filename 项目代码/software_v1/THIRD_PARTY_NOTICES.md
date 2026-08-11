# 第三方依赖声明

本项目调用下列第三方框架和库，但不把其源码、预训练权重或商标声明为本项目原创成果。实际分发前，应根据最终锁定版本再次核对对应许可证原文。

| 依赖 | 项目用途 | 上游许可证 |
| --- | --- | --- |
| PyTorch | 张量计算和ALBERT-GRU模型运行 | BSD-style |
| Hugging Face Transformers | ALBERT模型及Tokenizer接口 | Apache-2.0 |
| NumPy、pandas、scikit-learn | 特征处理和模型评估 | BSD-3-Clause |
| FastAPI、Pydantic、Uvicorn | Web API和数据契约 | MIT / BSD-3-Clause |
| SQLAlchemy、Alembic、PyMySQL | ORM、迁移和MySQL驱动 | MIT |
| Vue、Vue Router、Vite、Vitest | 前端、构建和测试 | MIT |
| TypeScript | 前端静态类型检查 | Apache-2.0 |
| Lucide | 界面图标 | ISC |
| Nginx | Docker部署中的静态文件和反向代理 | BSD-2-Clause |
| MySQL Community Server | 独立数据库服务 | GPL-2.0 |

权威许可证来源应以各依赖实际安装包中的`LICENSE`文件和上游发布仓库为准。`pyproject.toml`和`package-lock.json`用于记录本项目直接依赖及解析版本；Docker基础镜像中的间接依赖需要在正式交付镜像中另行生成软件物料清单。
