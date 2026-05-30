# PLAN-10: 支付宝周期扣款（自动续费）

## 概述

将现有的支付宝一次性支付（`alipay.trade.page.pay`）升级为周期扣款模式（`alipay.user.agreement.page.sign` + `alipay.trade.pay`），实现用户签约后自动按月扣费续期。

**当前状态**: 用户每月需手动访问 Pricing 页面重新支付续费。
**目标状态**: 用户首次支付时勾选自动续费，后续每月自动从支付宝扣款续期。

---

## 一、支付宝周期扣款流程

```
用户点击「升级」
    ↓
前端传入 auto_renew=true
    ↓
后端判断：auto_renew ?
    ├─ 否 → 走现有 alipay.trade.page.pay（不变）
    └─ 是 → 走签约流程 ↓
        ↓
调用 alipay.user.agreement.page.sign（签约）
    ↓
用户在支付宝页面授权签约
    ↓
支付宝回调 → 记录签约协议号 (agreement_no)
    ↓
首次扣款：alipay.trade.pay（用 agreement_no 扣款）
    ↓
激活会员 tier
    ↓
定时任务：每月到期前 1 天检查并自动扣款
    ↓
用户可随时取消签约（前端 + 支付宝 app 双向）
```

### 关键 API

| API | 用途 | 调用时机 |
|-----|------|---------|
| `alipay.user.agreement.page.sign` | 签约页面 | 用户首次勾选自动续费 |
| `alipay.user.agreement.query` | 查询签约状态 | 签约回调 / 用户查看 |
| `alipay.user.agreement.unsign` | 解约 | 用户取消自动续费 |
| `alipay.trade.pay` | 协议扣款 | 首次扣款 + 每月自动续费 |
| `alipay.trade.query` | 查询扣款结果 | 扣款后确认 |

---

## 二、数据库变更

### 新增表：`pay_agreements`（签约协议）

文件：`app/models/agreement.py`（新建）

```python
class Agreement(db.Model):
    __tablename__ = "pay_agreements"

    id = Column(String(16), primary_key=True)          # 内部 ID
    user_id = Column(String(16), nullable=False, index=True)
    agreement_no = Column(String(64), unique=True)      # 支付宝协议号
    external_agreement_no = Column(String(64))           # 我们传给支付宝的外部签约号
    provider = Column(String(16), default='alipay')      # alipay
    tier = Column(String(16), nullable=False)            # 签约档位
    status = Column(String(16), default='pending')       # pending / signed / cancelled / expired
    sign_time = Column(DateTime)                         # 签约时间
    cancel_time = Column(DateTime)                       # 解约时间
    next_deduct_date = Column(DateTime)                  # 下次扣款日期
    last_deduct_status = Column(String(16))              # 上次扣款结果: success / failed
    fail_count = Column(Integer, default=0)              # 连续失败次数
    created_at = Column(DateTime, default=bj_now)
```

### 修改表：`orders`（订单）

新增字段：

```python
agreement_id = Column(String(16), nullable=True, index=True)  # 关联签约协议
auto_renew = Column(Boolean, default=False)                    # 是否自动续费订单
deduct_type = Column(String(16), default='manual')            # manual / auto（区分手动/自动扣款）
```

迁移脚本：`migrations/add_agreement_fields.py`

---

## 三、后端实现

### 3.1 签约服务

文件：`app/services/payment_alipay.py`（扩展）

#### `create_sign_payment(order, agreement)`

签约 + 首次扣款流程入口：

```python
def create_sign_payment(order):
    """创建签约支付（周期扣款入口）"""
    alipay = _get_alipay()
    external_agreement_no = f'AH_{order.user_id}_{order.tier}_{int(time.time())}'

    # 1. 构造签约参数
    sign_params = {
        'external_agreement_no': external_agreement_no,
        'personal_product_code': 'CYCLE_PAY_AUTH_P',  # 周期扣款产品码
        'sign_scene': 'INDUSTRY|DIGITAL_MEDIA',         # 签约场景
        'access_params': {'channel': 'ALIPAYAPP'},
        'period_rule_params': {
            'period_type': 'MONTH',
            'period': 1,
            'execute_time': datetime.now().strftime('%d'),
            'single_amount': str(TIER_PRICES[order.tier] / 100),  # 单次扣款金额
        },
        'product_code': 'GENERAL_WITHHOLDING',
    }

    # 2. 生成签约页面 URL
    order_string = alipay.api_alipay_user_agreement_page_sign(
        **sign_params,
        return_url=f'{site_url}/checkout?status=sign_success&order={order.id}',
        notify_url=f'{site_url}/api/v1/payments/callback/alipay_sign',
    )
    sign_url = f'https://openapi.alipay.com/gateway.do?{order_string}'

    # 3. 创建 Agreement 记录
    agreement = Agreement(
        user_id=order.user_id,
        external_agreement_no=external_agreement_no,
        provider='alipay',
        tier=order.tier,
        status='pending',
    )
    db.session.add(agreement)
    order.agreement_id = agreement.id
    order.auto_renew = True
    db.session.commit()

    return {'checkout_url': sign_url, 'agreement_id': agreement.id}, None
```

#### `deduct_with_agreement(agreement)`

使用协议号扣款：

```python
def deduct_with_agreement(agreement):
    """通过签约协议号发起扣款"""
    alipay = _get_alipay()
    amount_yuan = TIER_PRICES[agreement.tier] / 100

    order = Order(
        user_id=agreement.user_id,
        tier=agreement.tier,
        amount=TIER_PRICES[agreement.tier],
        currency='cny',
        provider='alipay',
        agreement_id=agreement.id,
        auto_renew=True,
        deduct_type='auto',
    )
    db.session.add(order)
    db.session.commit()

    result = alipay.api_alipay_trade_pay(
        out_trade_no=order.id,
        total_amount=str(amount_yuan),
        subject=f'IntelHub {TIER_NAMES.get(agreement.tier)} · 月度自动续费',
        product_code='CYCLE_PAY_AUTH',
        agreement_params={'agreement_no': agreement.agreement_no},
    )

    if result.get('code') == '10000':
        order.status = 'paid'
        order.provider_id = result.get('trade_no', '')
        order.paid_at = bj_now()
        _activate_tier(order.user_id, order.tier)
        agreement.last_deduct_status = 'success'
        agreement.fail_count = 0
        agreement.next_deduct_date = bj_now() + timedelta(days=31)
        db.session.commit()
        return True
    else:
        order.status = 'failed'
        agreement.last_deduct_status = 'failed'
        agreement.fail_count = Agreement.fail_count + 1
        db.session.commit()
        return False
```

### 3.2 签约回调

文件：`app/api/payments.py`（扩展）

#### `POST /api/v1/payments/callback/alipay_sign`

```python
@bp.route('/callback/alipay_sign', methods=['POST'])
def alipay_sign_callback():
    """支付宝签约回调"""
    data = request.form.to_dict()
    signature = data.pop('sign', None)
    data.pop('sign_type', None)

    if not verify_callback(data, signature):
        return 'fail', 200

    # 签约成功通知
    if data.get('notify_type') == 'sign_success':
        external_agreement_no = data.get('external_agreement_no')
        agreement_no = data.get('agreement_no')

        agreement = Agreement.query.filter_by(
            external_agreement_no=external_agreement_no
        ).first()
        if not agreement:
            return 'success', 200

        agreement.agreement_no = agreement_no
        agreement.status = 'signed'
        agreement.sign_time = bj_now()
        agreement.next_deduct_date = bj_now() + timedelta(days=31)

        # 首次扣款
        deduct_with_agreement(agreement)
        db.session.commit()

    # 解约通知
    elif data.get('notify_type') == 'unsignd':
        agreement_no = data.get('agreement_no')
        agreement = Agreement.query.filter_by(agreement_no=agreement_no).first()
        if agreement:
            agreement.status = 'cancelled'
            agreement.cancel_time = bj_now()
            db.session.commit()

    return 'success', 200
```

### 3.3 前端 API 端点

#### `POST /api/v1/payments/create-order`（修改）

新增参数 `auto_renew`：

```python
@bp.route('/create-order', methods=['POST'])
@login_required
def create_order():
    data = request.get_json() or {}
    tier = data.get('tier', '')
    provider = data.get('provider', '')
    auto_renew = data.get('auto_renew', False)  # 新增

    # ... 校验不变 ...

    order = Order(...)
    if auto_renew and provider == 'alipay':
        db.session.add(order)
        db.session.commit()
        return create_sign_payment(order)  # 走签约流程
    else:
        # 走现有一次性支付流程（不变）
        ...
```

#### `POST /api/v1/payments/cancel-auto-renew`

```python
@bp.route('/cancel-auto-renew', methods=['POST'])
@login_required
def cancel_auto_renew():
    """用户主动取消自动续费"""
    user = g.current_user
    agreement = Agreement.query.filter_by(
        user_id=user.id, status='signed'
    ).first()
    if not agreement:
        return error_response(404, '无有效签约')

    # 调用支付宝解约
    from app.services.payment_alipay import cancel_agreement
    ok, err = cancel_agreement(agreement.agreement_no)
    if ok:
        agreement.status = 'cancelled'
        agreement.cancel_time = bj_now()
        db.session.commit()

    return standard_response({'cancelled': ok})
```

#### `GET /api/v1/payments/agreement`

```python
@bp.route('/agreement', methods=['GET'])
@login_required
def get_agreement():
    """查询当前用户的签约状态"""
    user = g.current_user
    agreement = Agreement.query.filter_by(user_id=user.id)\
        .filter(Agreement.status.in_(['signed', 'pending'])).first()
    if not agreement:
        return standard_response(None)
    return standard_response({
        'status': agreement.status,
        'tier': agreement.tier,
        'next_deduct_date': agreement.next_deduct_date.isoformat() if agreement.next_deduct_date else None,
        'sign_time': agreement.sign_time.isoformat() if agreement.sign_time else None,
    })
```

### 3.4 自动扣款定时任务

文件：`app/__init__.py`（扩展 scheduler）

```python
def _auto_deduct_check(app):
    """每日检查并执行自动扣款"""
    with app.app_context():
        from app.models.agreement import Agreement
        from app.services.payment_alipay import deduct_with_agreement
        now = bj_now()

        # 查找明天到期的有效签约
        agreements = Agreement.query.filter(
            Agreement.status == 'signed',
            Agreement.next_deduct_date <= now + timedelta(days=1),
        ).all()

        for agr in agreements:
            try:
                success = deduct_with_agreement(agr)
                if not success and agr.fail_count >= 3:
                    # 连续失败 3 次自动解约
                    agr.status = 'expired'
                    db.session.commit()
                    logger.warning('Auto-deduct failed 3 times, expired agreement %s', agr.id)
            except Exception as e:
                logger.error('Auto-deduct error for agreement %s: %s', agr.id, e)
```

注册定时任务：每天 02:00 执行（`_check_tier_expiry` 之后）

---

## 四、前端变更

### 4.1 Pricing.jsx — 增加自动续费选项

在支付按钮区域增加勾选框：

```jsx
// 状态
const [autoRenew, setAutoRenew] = useState(true)

// 在 handleUpgrade 中传入 auto_renew 参数
const handleUpgrade = async (tier) => {
    const provider = 'alipay'  // 或 stripe
    const { data } = await api.post('/api/v1/payments/create-order', {
        tier,
        provider,
        auto_renew: autoRenew,  // 新增
    })
    // ...
}

// 自动续费勾选框（放在卡片下方或支付确认弹窗中）
<label className="flex items-center gap-2 text-xs text-slate-400 mt-3">
    <input type="checkbox" checked={autoRenew} onChange={e => setAutoRenew(e.target.checked)}
        className="rounded border-slate-600 bg-slate-800 text-blue-500" />
    自动续费（每月自动扣款，可随时取消）
</label>
```

### 4.2 Profile.jsx — 展示签约状态

在个人信息页增加「自动续费」状态卡片：

```jsx
// 获取签约状态
const [agreement, setAgreement] = useState(null)
useEffect(() => {
    api.get('/api/v1/payments/agreement').then(res => {
        setAgreement(res.data?.data)
    }).catch(() => {})
}, [])

// 展示
{agreement?.status === 'signed' && (
    <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
        <div className="flex items-center justify-between">
            <div>
                <h4 className="text-white text-sm font-medium">自动续费</h4>
                <p className="text-xs text-slate-500 mt-1">
                    下次扣款：{agreement.next_deduct_date?.slice(0, 10)}
                </p>
            </div>
            <button onClick={handleCancelAutoRenew}
                className="text-xs text-red-400 hover:text-red-300">
                取消自动续费
            </button>
        </div>
    </div>
)}
```

### 4.3 Checkout.jsx — 处理签约回调

```jsx
// 新增签约成功的处理
const params = new URLSearchParams(location.search)
const signStatus = params.get('status')

if (signStatus === 'sign_success') {
    // 签约成功，轮询检查扣款结果
    // 逻辑与现有的支付成功轮询相同
}
```

---

## 五、支付宝后台配置

在支付宝开放平台需额外配置：

1. **签约产品码**: `CYCLE_PAY_AUTH_P`（周期扣款产品码）
2. **产品签约**: 在应用详情中添加「周期扣款」能力并签约
3. **签约场景**: `INDUSTRY|DIGITAL_MEDIA`（数字媒体行业）
4. **扣款最大金额**: 单次不超过订单金额
5. **回调地址**: 新增 `/api/v1/payments/callback/alipay_sign`

> 注意：签约场景需要与支付宝人工审核，预计 1-3 个工作日。

---

## 六、实现顺序

| 步骤 | 内容 | 文件 |
|------|------|------|
| 1 | 创建 Agreement 模型 + 数据库迁移 | `app/models/agreement.py`, `migrations/` |
| 2 | Order 模型新增字段 | `app/models/order.py`, `migrations/` |
| 3 | 扩展 payment_alipay.py 签约/扣款/解约方法 | `app/services/payment_alipay.py` |
| 4 | 新增签约回调 + 修改 create-order | `app/api/payments.py` |
| 5 | 定时任务：自动扣款检查 | `app/__init__.py` |
| 6 | 前端 Pricing.jsx 自动续费选项 | `frontend/src/pages/Pricing.jsx` |
| 7 | 前端 Profile.jsx 签约状态展示 | `frontend/src/pages/Profile.jsx` |
| 8 | 前端 Checkout.jsx 签约回调处理 | `frontend/src/pages/Checkout.jsx` |
| 9 | 支付宝后台配置 + 审核 | 线上操作 |

---

## 七、错误处理与边界

| 场景 | 处理方式 |
|------|---------|
| 签约成功但首次扣款失败 | Agreement 标记 signed，订单标记 failed；用户仍可手动支付激活 |
| 自动扣款失败 | `fail_count++`，连续 3 次失败自动解约并通知用户 |
| 用户余额不足 | 扣款失败，支付宝会重试 1 次（T+1），仍失败则计入 fail_count |
| 用户在支付宝 App 解约 | 回调通知更新状态，前端下次加载时展示已取消 |
| 用户降级/升级档位 | 取消旧签约 → 创建新签约（不同 tier 金额不同） |
| 用户取消自动续费后到期 | tier 正常过期降为 free（走现有 `_check_tier_expiry` 逻辑） |
| Stripe 走自动续费 | Stripe 已原生支持 billing subscription，不在本方案范围内 |

---

## 八、测试验证

1. **签约流程**: 用户点击升级 → 跳转支付宝签约 → 回调触发 → 首次扣款成功 → tier 激活
2. **自动扣款**: 模拟到期 → 定时任务触发 → 自动扣款 → tier 续期
3. **解约（前端）**: 用户点击取消 → 调用解约 API → 签约状态更新
4. **解约（支付宝 App）**: 用户在支付宝解约 → 回调通知 → 状态更新
5. **扣款失败**: 模拟余额不足 → fail_count 递增 → 3 次后自动解约
6. **并发安全**: 同一用户不能重复签约（先解约再签新约）
