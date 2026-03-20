# 示例：AI 工具类改写

## 原文摘要

英文博客，介绍 ask-search 这个开源项目，可以让 AI agent 免费搜索网页。

## 改写输出

---

### 三问先行

1. **最值得说的 3 个点**：
   - AI agent 搜索不用付 API 费、不用把查询数据交给第三方
   - SearxNG 一个工具聚合 Google/Bing/DuckDuckGo，结果更全
   - 部署门槛低到离谱：Docker 拉一个镜像 + Caddy 反代，完事

2. **读者想解决什么问题**：用 Claude Code 这类 agent 时，搜索 API 要么贵、要么隐私没保障。想要一个免费、可控、数据不外泄的方案。

3. **可独立转发的金句**：
   - "搜索 API 收费 + 数据外泄，这两个坑一个开源项目全填了。"

---

### 标题选项

1. **数字型**：3 步搭一个免费搜索 API，AI agent 随便用
2. **反常识型**：为什么你不该用付费搜索 API 喂你的 AI agent
3. **故事型**：有人把 SearxNG 包了一层 CLI，agent 搜索这事彻底解决了

---

### 正文

有个问题一直困扰用 Claude Code、OpenClaw 这类 AI agent 的人：搜索怎么办？

付费 API 按次收费，查多了肉疼。免费方案呢，查询记录全交给第三方，隐私是个坑。

最近有人做了个开源项目叫 ask-search，把这两个问题一次解决了。

它的核心是 SearxNG——一个自托管的元搜索引擎。说人话就是：它能同时查 Google、Bing、DuckDuckGo，把结果汇总给你。跑在你自己服务器上，数据不出门。

ask-search 在 SearxNG 上面包了一层 CLI。agent 调用起来特别顺手，返回标题、链接、摘要，直接能接着分析。

部署也不复杂。Docker 拉一个 SearxNG 镜像，绑到本地端口。Caddy 做反代加个 Basic Auth，自动 HTTPS。整套流程半小时能跑通。

有个细节容易踩坑：SearxNG 默认只返回 HTML，agent 要用得改成 JSON 输出。配置文件加一行 `- json` 就行。

用起来就一行命令：

```
ask-search "Claude" --num 5 --engines google,bing
```

Claude Code 里直接说 "ask search Claude using google"，它就知道怎么干了。

---

一句话：**搜索这事，要么花钱买方便，要么花半小时买自由。**

马上能做的动作：去 GitHub 搜 ask-search，今晚就能跑起来。

---

### 自检

- 删掉形容词，意思在 ✓
- 一口气读完不走神 ✓
- 朋友会转发吗？技术圈会 ✓
