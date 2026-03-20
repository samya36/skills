# Claude Skills Starter for 窦窦

包含 10 个适合内容运营 / 网站排障 / 学习执行的 Claude Code skill 模板。

放置方式：
- 项目级：复制 `.claude/skills/` 到你的项目根目录
- 个人级：复制到 `~/.claude/skills/`

推荐同时准备：
- `./CLAUDE.md`：项目规则、命名规范、测试命令
- `.claude/skills/*/SKILL.md`：可复用工作流
- 脚本：音频巡检、死链检查、日志过滤（不要硬塞进 skill）

使用方式：
- 手动调用：`/skill-name 参数`
- 自动调用：为 skill 写清楚 `description`，并保持内容聚焦

建议：
1. 先启用 3-5 个核心 skill，不要一次上 10 个
2. 长 reference 拆到 `reference.md` / `examples.md`
3. 机械检查交给脚本，skill 负责判断框架与产出结构
