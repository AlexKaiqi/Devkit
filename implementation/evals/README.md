# Evals

`implementation/evals/` 负责把需求层的验收用例真正运行起来，并输出可回归的报告。

这里可以出现：

- runner 代码
- evidence bundle
- 评测报告
- baseline 输出
- 后续接入的 LLM judge 适配器

## 目录约定

| 目录 | 说明 |
|------|------|
| `runners/` | 评测运行器 |
| `reports/` | 评测输出报告 |

## 当前状态

当前先提供一个零依赖的 acceptance runner scaffold：

- 从 `requirements/acceptance/` 读取 JSON case
- 校验 case 结构
- 生成统一 report skeleton
- 为后续接 evidence trace 和 LLM judge 预留字段

## 示例

```bash
.venv/bin/python implementation/evals/runners/acceptance_runner.py \
  --case requirements/acceptance/core/task-continuation-001.json
```
