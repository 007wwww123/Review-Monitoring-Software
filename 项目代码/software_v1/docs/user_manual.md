# 操作说明书底稿

## 部署前准备

1. 准备Linux服务器、NVIDIA驱动、Docker、Docker Compose和MySQL持久化空间。
2. 将完整ALBERT-GRU融合检查点、本地ALBERT基础模型目录和Tokenizer放入受控模型目录。
3. 计算检查点、`configs/base.json`及训练/验证/测试数据的SHA-256。
4. 将真实值填写到`configs/model_manifest.json`，并把`status`改为`ready`。
5. 从`deploy/.env.example`生成部署环境文件，填写强密码和绝对宿主机路径。

Docker基础镜像标签需要根据云服务器CUDA驱动兼容性自行核实；仓库默认值只是部署模板，不能视为已经在目标服务器验证。

## 启动

```bash
cd software_v1/deploy
docker compose build
docker compose up -d mysql backend worker frontend
docker compose exec backend python /app/scripts/init_admin.py
```

管理员初始化前需要临时设置`INITIAL_ADMIN_USERNAME`和`INITIAL_ADMIN_PASSWORD`。初始化完成后立即删除这两个环境变量。

浏览器访问`http://服务器地址:8080`。V1.0前端连接FastAPI真实接口，不依赖Hugging Face在线API；模型和Tokenizer必须提前放在本地受控目录。

## 主要操作

- 单条检测：填写用户、商品、评分、带时区时间和评论文本；历史可以不填，后端会查询已有记录。
- 批量检测：上传模板数据后创建排队任务，页面轮询任务状态。
- 结果查看：查看最终真假、辅助匹配度、行为可用性、门控摘要和解释限制。
- 模型评估：管理员指定`DATASET_ROOT`内的TSV文件，系统运行真实融合模型并保存指标及文件哈希。
- 模型切换：V1.0不支持在线切换；更新manifest后重启后端和Worker。

## 验收

```bash
cd software_v1/backend
python -m pytest -q

cd ../frontend
npm test -- --run
npm run build
```

云端还必须执行完整检查点加载、GPU前向、MySQL迁移和Docker联调。未完成这些验证前，不能在软著材料中写成“已验证”。
