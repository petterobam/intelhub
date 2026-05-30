# PLAN-09 Phase 4：文件上传与摄入

> 对应 PLAN-05 → Phase 4  
> 涉及 REQ：REQ-08（用户文件上传）  
> 预计周期：2-3 周  
> 前置条件：Phase 3 完成（`user_dirs.py` 存在，用户 KB 可写入）

---

## 目标

V5 用户可以上传 PDF / TXT / Markdown / 网页 URL，内容自动解析后纳入个人知识库，AI 对话时可以引用这些私有材料。

---

## 任务清单

### T1 · 文件上传 API

**新建文件**：`app/api/uploads.py`  
路由前缀：`/api/v1/uploads`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/` | 列出已上传文件 | v5+ |
| POST | `/` | 上传文件（multipart/form-data）| v5+ |
| POST | `/url` | 提交网页 URL 抓取 | v5+ |
| DELETE | `/<id>` | 删除上传文件 | v5+，限本人 |
| GET | `/quota` | 查看存储配额 | v5+ |

**`POST /` 处理逻辑**：
```app/api/uploads.py#L1-30
@bp.route('', methods=['POST'])
@tier_required('v5')
def upload_file():
    if 'file' not in request.files:
        return error_response(400, '请选择文件')
    
    f = request.files['file']
    user_id = g.current_user.id
    
    # 1. 校验文件类型
    ext = f.filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return error_response(400, f'不支持的文件类型: .{ext}')
    
    # 2. 校验文件大小（10MB）
    f.seek(0, 2)
    size = f.tell()
    f.seek(0)
    if size > 10 * 1024 * 1024:
        return error_response(400, '文件不能超过 10MB')
    
    # 3. 校验存储配额
    if not _check_quota(user_id):
        return error_response(400, '存储空间已满（500MB），请删除旧文件后重试')
    
    # 4. 保存文件
    upload_id = uuid.uuid4().hex[:8]
    save_path = os.path.join(user_uploads_dir(user_id), f'{upload_id}.{ext}')
    assert_within_user_dir(user_id, save_path)   # 安全校验
    f.save(save_path)
    
    # 5. 写入数据库记录
    record = UserUpload(id=upload_id, user_id=user_id, filename=f.filename,
                        ext=ext, size=size, path=save_path)
    db.session.add(record)
    db.session.commit()
    
    # 6. 异步触发解析
    threading.Thread(target=_parse_and_ingest, args=(upload_id,), daemon=True).start()
    
    return standard_response({'id': upload_id, 'filename': f.filename, 'status': 'parsing'})

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'md', 'docx'}
```

**`POST /url` 处理逻辑**（网页 URL 抓取）：
```app/api/uploads.py#L1-15
@bp.route('/url', methods=['POST'])
@tier_required('v5')
def fetch_url():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    if not url.startswith(('http://', 'https://')):
        return error_response(400, '请输入有效的 HTTP/HTTPS URL')
    
    user_id = g.current_user.id
    upload_id = uuid.uuid4().hex[:8]
    
    # 异步抓取
    threading.Thread(
        target=_fetch_url_and_ingest,
        args=(upload_id, user_id, url),
        daemon=True,
    ).start()
    
    return standard_response({'id': upload_id, 'url': url, 'status': 'fetching'})
```

---

### T2 · UserUpload 数据模型

**新建文件**：`app/models/user_upload.py`

```app/models/user_upload.py#L1-25
class UserUpload(db.Model):
    __tablename__ = 'user_uploads'

    id          = Column(String(16), primary_key=True)
    user_id     = Column(String(16), ForeignKey('users.id'), nullable=False, index=True)
    filename    = Column(String(256), nullable=False)
    # 原始文件名（用于展示）
    ext         = Column(String(8), nullable=False)
    # pdf | txt | md | docx | url
    size        = Column(Integer, default=0)
    # 字节数，URL 类型为 0
    path        = Column(String(512), nullable=True)
    # 本地文件路径（URL 类型为空）
    source_url  = Column(String(1024), nullable=True)
    # 网页 URL（URL 类型）
    status      = Column(String(16), default='pending')
    # pending | parsing | ready | error
    parse_error = Column(Text, nullable=True)
    char_count  = Column(Integer, default=0)
    # 解析后字符数（估算 token 用）
    created_at  = Column(DateTime, default=datetime.utcnow)
    ingested_at = Column(DateTime, nullable=True)
    # 成功纳入 KB 的时间
```

**数据库迁移**：
```/dev/null/sql.sql#L1-18
CREATE TABLE user_uploads (
  id          VARCHAR(16) PRIMARY KEY,
  user_id     VARCHAR(16) NOT NULL REFERENCES users(id),
  filename    VARCHAR(256) NOT NULL,
  ext         VARCHAR(8) NOT NULL,
  size        INTEGER DEFAULT 0,
  path        VARCHAR(512),
  source_url  VARCHAR(1024),
  status      VARCHAR(16) DEFAULT 'pending',
  parse_error TEXT,
  char_count  INTEGER DEFAULT 0,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  ingested_at DATETIME
);
```

---

### T3 · 文件解析器

**新建目录**：`knowledge_base/parsers/`

**新建文件**：`knowledge_base/parsers/base.py`
```knowledge_base/parsers/base.py#L1-10
class BaseParser:
    def parse(self, path: str) -> dict:
        """
        返回：{
            'text': str,          # 提取的纯文本
            'title': str,         # 文档标题（可选）
            'char_count': int,    # 字符数
            'metadata': dict,     # 附加元数据
        }
        """
        raise NotImplementedError
```

**新建文件**：`knowledge_base/parsers/pdf_parser.py`（P0）：
```knowledge_base/parsers/pdf_parser.py#L1-15
import pdfminer.high_level

class PdfParser(BaseParser):
    def parse(self, path: str) -> dict:
        text = pdfminer.high_level.extract_text(path)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        # 第一行非空内容作为标题
        title = lines[0][:100] if lines else os.path.basename(path)
        return {
            'text': text,
            'title': title,
            'char_count': len(text),
            'metadata': {'source': 'pdf'},
        }
```

依赖：`requirements.txt` 追加 `pdfminer.six>=20221105`

**新建文件**：`knowledge_base/parsers/text_parser.py`（P0，处理 TXT / Markdown）：
```knowledge_base/parsers/text_parser.py#L1-10
class TextParser(BaseParser):
    def parse(self, path: str) -> dict:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        lines = text.split('\n')
        # Markdown 取第一个 # 标题，纯文本取第一行
        title = next((l.lstrip('#').strip() for l in lines if l.strip()), os.path.basename(path))
        return {'text': text, 'title': title, 'char_count': len(text), 'metadata': {'source': 'text'}}
```

**新建文件**：`knowledge_base/parsers/url_parser.py`（P1，网页抓取）：
```knowledge_base/parsers/url_parser.py#L1-20
import requests
from bs4 import BeautifulSoup

class UrlParser(BaseParser):
    def fetch_and_parse(self, url: str) -> dict:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(resp.text, 'lxml')
        
        # 提取正文（移除 script/style）
        for tag in soup(['script', 'style', 'nav', 'footer']):
            tag.decompose()
        text = soup.get_text(separator='\n', strip=True)
        title = soup.find('title')
        title = title.get_text(strip=True) if title else url
        
        return {'text': text, 'title': title, 'char_count': len(text),
                'metadata': {'source': 'url', 'url': url}}
```

**新建文件**：`knowledge_base/parsers/docx_parser.py`（P2）：
- 依赖 `python-docx>=1.1`
- 提取所有段落文本

**新建文件**：`knowledge_base/parsers/dispatcher.py` — 根据扩展名分发：
```knowledge_base/parsers/dispatcher.py#L1-12
PARSERS = {
    'pdf': PdfParser,
    'txt': TextParser,
    'md':  TextParser,
    'docx': DocxParser,
}

def get_parser(ext: str) -> BaseParser:
    cls = PARSERS.get(ext.lower())
    if not cls:
        raise ValueError(f'No parser for .{ext}')
    return cls()
```

---

### T4 · 解析后纳入用户 KB

**新建文件**：`knowledge_base/parsers/ingestor.py`  
职责：解析结果 → 分块 → 写入用户 KB 目录

```knowledge_base/parsers/ingestor.py#L1-30
def ingest_upload(upload_id: str):
    """解析上传文件并纳入用户 KB"""
    upload = db.session.get(UserUpload, upload_id)
    if not upload:
        return
    
    upload.status = 'parsing'
    db.session.commit()
    
    try:
        # 1. 解析
        if upload.ext == 'url':
            parser = UrlParser()
            result = parser.fetch_and_parse(upload.source_url)
        else:
            parser = get_parser(upload.ext)
            result = parser.parse(upload.path)
        
        # 2. 写入用户 uploads KB 目录
        kb_uploads_dir = os.path.join(user_kb_dir(upload.user_id), 'uploads')
        os.makedirs(kb_uploads_dir, exist_ok=True)
        assert_within_user_dir(upload.user_id, kb_uploads_dir)
        
        out_path = os.path.join(kb_uploads_dir, f'{upload_id}.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({
                'upload_id': upload_id,
                'title': result['title'],
                'text': result['text'][:50000],  # 限制长度，防止超大文件
                'char_count': result['char_count'],
                'metadata': result['metadata'],
                'ingested_at': datetime.now().isoformat(),
            }, f, ensure_ascii=False)
        
        # 3. 触发 KB 重建
        UserKBBuilder().build(upload.user_id)
        
        # 4. 更新状态
        upload.status = 'ready'
        upload.char_count = result['char_count']
        upload.ingested_at = datetime.utcnow()
        
    except Exception as e:
        upload.status = 'error'
        upload.parse_error = str(e)[:500]
    
    db.session.commit()
```

**修改文件**：`knowledge_base/user_kb_builder.py`  
在 `build()` 中追加加载 `uploads/` 目录的逻辑：
```knowledge_base/user_kb_builder.py#L1-10
def _load_upload_items(self, user_id: str) -> list:
    """加载用户上传文件解析结果"""
    uploads_dir = os.path.join(user_kb_dir(user_id), 'uploads')
    items = []
    if not os.path.exists(uploads_dir):
        return items
    for fname in os.listdir(uploads_dir):
        if fname.endswith('.json'):
            data = json.load(open(os.path.join(uploads_dir, fname)))
            # 把长文本拆分为段落，模拟多条目
            paragraphs = [p for p in data['text'].split('\n\n') if len(p.strip()) > 20]
            for p in paragraphs[:50]:  # 每个文件最多50段
                items.append({'title': data['title'], 'content': p,
                               '_source': 'upload', '_upload_id': data['upload_id']})
    return items
```

---

### T5 · 配额管理

**新建文件**：`app/utils/quota.py`

```app/utils/quota.py#L1-20
TIER_QUOTAS = {
    'v5': {
        'storage_bytes': 500 * 1024 * 1024,   # 500MB
        'monthly_uploads': 50,
    }
}

def get_used_storage(user_id: str) -> int:
    """返回用户 uploads 目录总大小（字节）"""
    uploads_dir = user_uploads_dir(user_id)
    if not os.path.exists(uploads_dir):
        return 0
    total = sum(os.path.getsize(os.path.join(uploads_dir, f))
                for f in os.listdir(uploads_dir)
                if os.path.isfile(os.path.join(uploads_dir, f)))
    return total

def check_storage_quota(user_id: str, tier: str) -> bool:
    """返回 True 表示未超额"""
    quota = TIER_QUOTAS.get(tier, {}).get('storage_bytes', 0)
    return get_used_storage(user_id) < quota
```

---

### T6 · 前端上传页面

**新建文件**：`frontend/src/pages/Uploads.jsx`

页面结构：
- **上传区**：拖拽或点击上传（支持 PDF/TXT/MD/DOCX），显示文件大小限制提示
- **URL 输入**：输入框 + 「抓取」按钮，支持提交网页 URL
- **文件列表**：显示已上传文件（文件名、大小、状态徽章、上传时间）
  - 状态颜色：pending（灰）/ parsing（蓝，旋转图标）/ ready（绿）/ error（红，hover 显示错误信息）
- **配额进度条**：`已使用 12MB / 500MB`
- 每行可删除；ready 的文件右侧显示「已纳入知识库」

侧边栏：`v5+` 用户显示「上传文件」入口

**轮询状态**：上传后前端每 3 秒轮询 `GET /api/v1/uploads/` 直到 status 不再是 `pending/parsing`

---

## 文件清单汇总

| 操作 | 文件路径 |
|------|---------|
| **新建** | `app/models/user_upload.py` |
| **新建** | `app/api/uploads.py` |
| **新建** | `app/utils/quota.py` |
| **新建** | `knowledge_base/parsers/__init__.py` |
| **新建** | `knowledge_base/parsers/base.py` |
| **新建** | `knowledge_base/parsers/pdf_parser.py` |
| **新建** | `knowledge_base/parsers/text_parser.py` |
| **新建** | `knowledge_base/parsers/url_parser.py` |
| **新建** | `knowledge_base/parsers/docx_parser.py` |
| **新建** | `knowledge_base/parsers/dispatcher.py` |
| **新建** | `knowledge_base/parsers/ingestor.py` |
| **新建** | `frontend/src/pages/Uploads.jsx` |
| **修改** | `knowledge_base/user_kb_builder.py` — 追加加载 uploads/ |
| **修改** | `requirements.txt` — 追加 pdfminer.six、python-docx |
| **修改** | `frontend/src/App.jsx` — 追加「上传文件」路由 |

---

## 数据库迁移 SQL

```/dev/null/migration.sql#L1-14
CREATE TABLE user_uploads (
  id          VARCHAR(16) PRIMARY KEY,
  user_id     VARCHAR(16) NOT NULL REFERENCES users(id),
  filename    VARCHAR(256) NOT NULL,
  ext         VARCHAR(8) NOT NULL,
  size        INTEGER DEFAULT 0,
  path        VARCHAR(512),
  source_url  VARCHAR(1024),
  status      VARCHAR(16) DEFAULT 'pending',
  parse_error TEXT,
  char_count  INTEGER DEFAULT 0,
  created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
  ingested_at DATETIME
);
```

---

## 验收标准

1. **T1**：V5 用户通过 `POST /api/v1/uploads` 上传一个 PDF，响应返回 `{id, status: 'parsing'}`
2. **T3**：`PdfParser().parse('/path/to/test.pdf')` 返回包含文本内容的 dict
3. **T4**：上传 PDF 后等待 10 秒，`user_uploads` 表中该记录 `status` 变为 `ready`，`data/users/{user_id}/kb/uploads/` 下出现对应 JSON
4. **T5**：`GET /api/v1/uploads/quota` 返回已用空间和上限
5. **T6**：前端上传页面可以拖拽上传文件，文件列表实时刷新状态

---

## 注意事项

- **PDF 解析质量**：扫描版 PDF（纯图片）无法直接解析文本，建议在解析失败时提示用户「此 PDF 为扫描版，暂不支持」
- **大文件截断**：解析后文本超过 50,000 字符时截断，并在 metadata 中注明 `truncated: true`
- **URL 安全**：禁止抓取内网 IP 和 localhost（防 SSRF）

```app/api/uploads.py#L1-8
import re

BLOCKED_URL_PATTERNS = [
    r'^https?://(localhost|127\.|192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)',
]

def _is_safe_url(url: str) -> bool:
    return not any(re.match(p, url) for p in BLOCKED_URL_PATTERNS)
```
