# 迭代3: 爬虫迁移 + 分析系统升级

**目标**: 将 Hermes cron jobs 中已验证的成熟爬虫脚本完整迁移到 IntelHub 框架，并使用 Anthropic Claude SDK 实现多轮分析系统。

---

## 一、现状差距分析

### 热点采集
| 维度 | Hermes Cron | IntelHub 现状 |
|------|------------|---------------|
| 平台数 | 9个 (微博/抖音/知乎/36kr/虎嗅/东方财富/澎湃/网易/环球网) | 1个 (36kr API) |
| 数据量 | 每平台数十条/次 | 10条/次 |

### 政策采集
| 维度 | Hermes Cron | IntelHub 现状 |
|------|------------|---------------|
| 机构数 | 10个 (央行/证监会/财政部/中行/国务院/外管局/发改委/工信部/统计局/国资委) | 2个 (央行/国务院) |

### 巨潮/股票
| 维度 | Hermes Cron | IntelHub 现状 |
|------|------------|---------------|
| 覆盖 | 500+只A股 (273行config) | 未实现 |

### 交易所
| 维度 | Hermes Cron | IntelHub 现状 |
|------|------------|---------------|
| 交易所 | 4个 (SSE/SZSE/BSE/HKEX) | 2个 (SSE/SZSE) |

---

## 二、迁移方案

### Phase 1: 脚本迁移 (copied to crawlers/scripts/)

```
crawlers/
├── scripts/                          # 新增: 迁移的JS爬虫脚本
│   ├── hot_topics/                   # 热点平台爬虫
│   │   ├── weibo-crawler.js
│   │   ├── douyin-hot-crawler.js
│   │   ├── zhihu-crawler.js
│   │   ├── 36kr-crawler.js
│   │   ├── huxiu-crawler.js
│   │   ├── eastmoney-crawler.js
│   │   ├── paper-crawler.js
│   │   ├── wangyi-browser-crawler.js
│   │   └── huanqiu-crawler.js
│   ├── policy/                       # 政策监控爬虫
│   │   ├── policy_pbc.js
│   │   ├── policy_csrc.js
│   │   ├── policy_mof.js
│   │   ├── policy_boc.js
│   │   ├── policy_gov.js
│   │   ├── policy_safe.js
│   │   ├── policy_ndrc.js
│   │   ├── policy_miit.js
│   │   ├── policy_stats.js
│   │   └── policy_sasac.js
│   ├── exchange/                     # 交易所爬虫
│   │   ├── exchange-sse.js
│   │   ├── exchange-szse.js
│   │   ├── exchange-bse.js
│   │   └── exchange-hkex.js
│   ├── financial/                    # 巨潮资讯爬虫
│   │   ├── cninfo-hermes-crawler.js
│   │   └── cninfo-stocks-expanded.config
│   └── utils/                        # 共享工具
│       ├── deduplicate-data.py
│       └── normalize-fields.py
├── hot_topics/runner.py              # 重写: 调用JS脚本
├── policy/runner.py                  # 重写: 调用JS脚本
├── exchange/runner.py                # 重写: 调用JS脚本
└── financial/runner.py               # 重写: 调用JS脚本
```

### Phase 2: Runner 重写策略

每个 Runner 改为两种模式:
1. **JS模式**: `subprocess.run(['node', script_path])` - 调用迁移的JS脚本
2. **Fallback模式**: 原有 Python requests 方式 - JS脚本失败时的降级

```python
class HotTopicsRunner:
    def run_all(self):
        results = []
        for platform in platforms:
            result = self._run_js_crawler(platform)  # 优先JS
            if result['status'] != 'success':
                result = self._fallback_python(platform)  # 降级
            results.append(result)
        return results
    
    def _run_js_crawler(self, platform):
        script = os.path.join(SCRIPTS_DIR, 'hot_topics', f'{platform}-crawler.js')
        proc = subprocess.run(['node', script], capture_output=True, text=True, timeout=120)
        # 解析输出/文件获取结果
```

### Phase 3: 数据目录统一

JS脚本输出路径从旧目录重定向到 IntelHub 的 `data/raw/`:
- `data/raw/hot_topics/{platform}/` - 每个平台一个子目录
- `data/raw/policy/{agency}/` - 每个机构一个子目录  
- `data/raw/exchange/{sse,szse,bse,hkex}/`
- `data/raw/financial/cninfo/`

---

## 三、执行步骤

### Step 1: 创建目录 + 复制脚本
- `mkdir -p crawlers/scripts/{hot_topics,policy,exchange,financial,utils}`
- 复制9个热点爬虫 JS
- 复制10个政策爬虫 JS
- 复制4个交易所爬虫 JS
- 复制 cninfo 爬虫 + 500股config
- 复制去重/标准化工具

### Step 2: 修改JS脚本输出路径
每个JS脚本的输出路径需要适配 IntelHub 的 `data/raw/` 目录结构。
通过环境变量 `OUTPUT_DIR` 控制。

### Step 3: 重写4个Runner
- HotTopicsRunner: 调用9个JS脚本 + fallback
- PolicyRunner: 调用10个JS脚本 + fallback
- ExchangeRunner: 调用4个JS脚本 + fallback
- FinancialRunner: 调用cninfo批量脚本 + fallback

### Step 4: 更新cron_wrapper shell脚本
适配新的runner接口。

### Step 5: 更新DB种子数据
扩展任务定义，增加每个平台/机构的子任务。

### Step 6: 端到端测试
每个采集器独立测试，验证数据产出。

---

## 四、关键决策

1. **JS脚本不修改核心逻辑**, 只调整输出路径
2. **Runner 负责 JS ↔ Python 桥接**, 统一异常处理和结果格式
3. **保留 fallback**, JS 失败时用 requests 降级
4. **数据去重和标准化**, 在 Runner.run_all() 完成后自动执行
