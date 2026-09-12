# ANCHOR 1.0

ANCHOR 是面向“一名人类决策者 + AI 执行者”的轻量项目控制体系。

它通过项目原生文件保存规则、状态、需求、决策、证据和审计记录，降低跨会话遗忘、范围漂移、越界修改和未验证交付的风险。

## 快速开始

1. 将本仓库内容复制到新项目根目录。
2. 根据项目实际情况填写 `state.yaml`。
3. 使用 `templates/` 创建第一条需求、设计、任务和验证计划。
4. 开始工作前运行：

```bash
python3 scripts/anchor-recover.py
python3 scripts/anchor-validate.py
```

5. 修改控制脚本后运行完整测试：

```bash
python3 -m py_compile scripts/*.py
python3 scripts/test-anchor-recovery.py
python3 scripts/test-anchor-sandbox.py
bash scripts/check-control-system.sh
git diff --check
```

## 阅读顺序

- 第一次了解：`docs/control/ANCHOR-1.0-说明.md`
- 正式协议：`docs/control/ANCHOR-1.0.md`
- 项目规则：`AGENTS.md`
- 模板：`templates/`

## 版本

当前版本：`1.0.0`

本仓库只包含 ANCHOR 通用控制体系，不包含任何具体项目的需求、业务资料、代码或验收记录。
