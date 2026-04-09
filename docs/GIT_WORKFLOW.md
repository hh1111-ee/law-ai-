# Git 工作流与回滚指南

推荐最小流程，便于多人协作且能回退接口变更：

1. 分支策略
   - `main`：稳定、可部署的主分支。
   - `develop`：日常开发集成分支（可选，若习惯 trunk-based 可直接在 feature -> main）。
   - `feature/*`：每个后端接口或功能使用独立的 `feature/xxx` 分支开发。
   - `hotfix/*`：生产紧急修复分支。

2. 版本与发布
   - 每次向 `main` 合并并验证后，打 tag：`vMAJOR.MINOR.PATCH`，例如 `git tag -a v0.1.0 -m "Release v0.1.0"` 然后 `git push --follow-tags`。

3. 回退（rollback）
   - 回退到某个已知稳定的 tag：
     ```bash
     git checkout main
     git reset --hard v0.1.0
     git push --force-with-lease origin main
     ```
   - 或用 revert（保留历史）:
     ```bash
     git revert <bad-commit-hash>
     git push origin main
     ```

4. 代码审查与 CI
   - 使用 PR（Pull Request）合并到 `main` 或 `develop`，并在 CI 中运行测试/接口契约检查。

5. 钩子与防护
   - 使用仓库自带的 `.githooks/pre-commit`（或配置 `core.hooksPath`）以阻止意外提交敏感文件。
