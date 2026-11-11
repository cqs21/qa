# Asterinas QA 页面预览

静态 QA 页面，包含 Overview、Test coverage、API coverage、Performance 和 Methods & data 五个视图。
默认展示从 GitHub Actions、Asterinas Book 和 benchmark 导入的真实数据样本；`?dataset=demo` 展示明确标记的虚构交互示例。
浏览器读取静态 JSON，无需 npm 构建、账户、GitHub token 或后端服务。

## 本地预览

以下命令均在本目录执行；如果当前位于 Asterinas 主仓库根目录，先运行 `cd qa`。

```bash
python3 -m http.server 8080 --bind 127.0.0.1
```

打开 `http://localhost:8080/`。
远程容器可转发 TCP 8080；结束预览时按 Ctrl+C。

| 入口 | 内容 |
| --- | --- |
| `/` | main 上启用 workflow 的结果统计、分组列表与最新 run 链接；跨 workflow 测试矩阵、API 和性能摘要 |
| `/?view=tests` | 各测试配置最新执行与上一次成功，NixOS 大类及应用子套件，原生计数、筛选和执行详情 |
| `/?view=api` | syscall 状态、flags 限制、SCML、搜索和 Book 来源 |
| `/?view=performance` | benchmark 指标原值、历史数据点与等价表格 |
| `/?view=methods` | 数据来源、版本、时间、统计口径、证据与下载入口 |
| `/?dataset=demo` | 虚构的失败、阻断、取消和缺报告等交互示例 |

筛选和详情保存在 URL 查询参数中，支持刷新、分享和浏览器前进/后退。
资源使用相对路径，因此同一页面可直接部署到 `/qa/`，无需更改 base URL 或配置服务端路由。

## 数据与保留范围

| 文件或目录 | 用途 |
| --- | --- |
| `data/real.json` | 页面默认读取的 workflow、测试、API 和性能观察数据 |
| `data/demo.json`、`data/schema-v1.json`、`data/boot-example.log` | 虚构交互示例、其 schema 和示例日志 |
| `data/sources/manifest.json` | 真实来源清单、固定版本、采集时间和原始字节 SHA-256 |
| `data/sources/*.gz` | 原始 API 响应、Book、benchmark 和日志；用于离线重建、校验及页面证据下载 |

`data/sources/` 当前所有归档都有清单引用，页面的来源列表和执行详情也提供下载入口。
这些文件支持预览复核，直接删除会使离线重建或证据下载失效。
生产接入后可以将完整归档移到独立数据存储，Pages 仅发布需要的摘要与证据；迁移时需同步调整读取与下载链接。

真实测试结果按每个配置分别选择最新实际执行及上一次成功。
新 run 未执行某项时保留旧记录，失败和取消仍按原结论展示；重跑克隆的成功 job 指向原执行。
只接收主仓库 main 的 `push`、`schedule`、`workflow_dispatch`，PR、fork 和其他分支的结果不会进入公开测试汇总。
当前观察键来自 workflow path、job 名称和平台，尚不能替代正式 CI 报告中的稳定配置标识。

NixOS 是一个测试大类，各应用子套件分别保留记录。
其原生计数只读取完整的宿主框架摘要，不混入应用内部 assertions；缺摘要与缺日志分别说明。
不同套件的原生计数单位不跨套件累加为总体通过率。

API 是固定 Book 提交上的支持声明，不等同于运行测试覆盖率。
性能唯一来源为 `asterinas/benchmark`，保留原值、单位与历史；环境和实际被测提交未知时不推断性能倍率。
各来源保留自己的版本和时间，页面重新发布不会使旧结果变成新结果。

## 刷新与校验

导入器仅使用 Python 3 标准库。
刷新需要已认证的 GitHub CLI（`gh`），只访问读取接口；离线重建与真实数据校验不访问网络。

```bash
# 离线重建默认页面数据并校验。
PYTHONDONTWRITEBYTECODE=1 python3 tools/import_real.py
PYTHONDONTWRITEBYTECODE=1 python3 tools/check_real.py

# 独立刷新 main 执行历史与 NixOS 日志、Book 或 benchmark。
python3 tools/import_real.py --refresh-main
python3 tools/import_real.py --refresh-book
python3 tools/import_real.py --refresh-benchmark

# 补收当前 NixOS 记录的日志，或刷新全部来源。
python3 tools/import_real.py --refresh-nixos-logs
python3 tools/import_real.py --refresh
```

多个刷新选项可组合使用，未刷新的来源保持原版本。
生产收集应先恢复持久历史，不能每次仅从固定样本重建。

虚构数据使用独立的生成器和校验器；只有此校验器需要 `jsonschema`：

```bash
python3 -m venv /tmp/asterinas-qa-check
/tmp/asterinas-qa-check/bin/pip install -r tools/requirements.txt
/tmp/asterinas-qa-check/bin/python tools/check_demo.py

# 需要重新生成虚构示例时运行，不改变真实来源。
python3 tools/generate_demo.py
```

## 源码组织

| 文件 | 职责 |
| --- | --- |
| `index.html`、`styles.css`、`assets/` | 页面入口、样式和图形资源 |
| `app.js`、`model.js` | 路由、数据读取、下载和示例数据索引 |
| `ci-model.js`、`main-views.js` | workflow 统计、测试矩阵、NixOS 子套件、历史成功及执行详情 |
| `real-views.js` | API、性能及真实来源展示 |
| `views.js` | 共用外壳、图标和虚构示例视图 |
| `tools/import_real.py`、`tools/main_results.py` | 来源采集、日志解析、历史合并和离线重建 |
| `tools/check_real.py` | 来源完整性、计数、事件过滤、重跑及历史选择验证 |
| `tools/generate_demo.py`、`tools/check_demo.py` | 虚构示例生成与校验 |
| `.github/workflows/pages.yml` | 独立仓库的静态 Pages 校验与部署 |

标志源自 Asterinas Book 的 SVG；页面使用系统字体、原生 ES modules 和 SVG，没有外部 CDN 依赖。
