# 抖音喜欢列表 API 调试指南

## 问题现象
代码只抓取了 2 页（37-39个视频）就停止，无法获取全部喜欢的视频。

## 使用 Chrome DevTools 手动调试步骤

### 1. 打开 Chrome DevTools
1. 访问 `https://www.douyin.com/user/self?showTab=like`
2. 按 `F12` 或右键 → "检查" 打开 DevTools
3. 切换到 **Network（网络）** 标签

### 2. 过滤 API 请求
1. 在 Filter 框中输入: `aweme/favorite`
2. 或输入: `aweme/v1/web`

### 3. 手动滚动测试
1. **初始加载**：页面加载后，查看第一个 `aweme/favorite` 请求
   - 点击请求 → 切换到 **Response** 标签
   - 记录 `aweme_list` 数组长度（通常是 18-20）

2. **查看请求参数**（Preview 或 Headers 标签）：
   ```
   关键参数：
   - max_cursor: 分页游标（用于获取下一页）
   - count: 每页数量（通常是 18 或 20）
   - sec_user_id: 用户ID
   ```

3. **手动滚动触发下一页**：
   - 慢慢滚动到页面底部
   - 观察是否有新的 `aweme/favorite` 请求
   - 记录新请求的 `max_cursor` 值

### 4. 检查关键信息

#### A. 总共有多少个喜欢的视频？
**方法 1**: 在 Console 中执行：
```javascript
// 查看页面上的视频数量
document.querySelectorAll('[data-e2e="feed-item"]').length
```

**方法 2**: 查看最后一个 API 响应：
```json
{
  "aweme_list": [...],
  "max_cursor": 1773257891000,
  "has_more": 0  // ← 关键字段：是否还有更多数据
}
```

#### B. API 响应结构
查看 Response 中的完整结构：
```json
{
  "status_code": 0,
  "has_more": 0 或 1,  // 是否还有更多数据
  "max_cursor": 1773257891000,  // 下一页的游标
  "aweme_list": [
    {"aweme_id": "...", "desc": "..."},
    ...
  ]
}
```

### 5. 常见问题排查

#### 问题 1: 滚动后没有新的 API 请求
**可能原因**：
- 滚动速度太快，未触发懒加载
- 需要滚动到特定位置
- 页面检测到自动化，阻止了加载

**解决方法**：
- 尝试分段滚动：
  1. 滚动到接近底部（留 200px）
  2. 等待 2-3 秒
  3. 继续滚动到底部
  4. 等待 3-5 秒

#### 问题 2: API 响应中没有 `has_more` 字段
**说明**：抖音的 API 结构可能会变化，可能需要通过其他方式判断是否还有数据：
- `aweme_list` 数组长度（如果小于每页数量，可能是最后一页）
- 连续滚动后不再有新的 API 请求

#### 问题 3: 只有 2-3 页数据
**检查**：
1. 手动在浏览器中滚动，看能加载多少页
2. 如果手动也只能加载 2-3 页，说明账号的喜欢列表确实只有这么多数据
3. 如果手动能加载更多，说明代码的滚动策略有问题

### 6. 收集诊断信息

请记录以下信息，以便进一步调试：

```
1. 手动滚动能加载多少页？
   - 第1页: __ 个视频
   - 第2页: __ 个视频
   - 第3页: __ 个视频
   - 总共: __ 页

2. 最后一个 API 的响应：
   - aweme_list 长度: __
   - has_more: __
   - max_cursor: __

3. 请求 URL 示例：
   （复制一个完整的 aweme/favorite 请求 URL）

4. 滚动策略：
   - 滚动几次后出现新的 API？
   - 需要等待多长时间？
```

### 7. 对比代码行为

**当前代码的滚动策略**：
```python
# 1. 滚动到接近底部
await page.evaluate("window.scrollTo(0, document.body.scrollHeight - 500)")
await page.wait_for_timeout(2000)

# 2. 滚动到绝对底部
await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
await page.wait_for_timeout(2000)

# 3. 增量滚动
await page.evaluate("window.scrollBy(0, 300)")
await page.wait_for_timeout(1000)

# 4. 再次滚动到底部
await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
await page.wait_for_timeout(3000)

# 5. 等待 API (最多30秒)
data = await self.interceptor.wait_for("aweme/favorite", timeout=30)
```

**手动测试时请观察**：
1. 哪个步骤触发了新的 API？
2. 需要等待多久？
3. 是否需要特定的滚动位置？

## 临时解决方案

如果发现手动滚动能加载更多数据，但代码不行，可能需要：

1. **增加等待时间**
2. **改进滚动策略**（模仿真实用户行为）
3. **使用鼠标滚动**而非 JavaScript 滚动
4. **添加随机延迟**避免被检测

## 下一步

完成以上调试后，请提供：
1. 手动滚动的结果（能加载几页）
2. 截图或复制关键 API 响应
3. 滚动行为的观察结果

这样我可以针对性地修复代码。
