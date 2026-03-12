## ADDED Requirements

### Requirement: Browser lifecycle management
系统 SHALL 管理单个 Playwright Chromium 浏览器实例的启动、停止和页面复用。使用 persistent context 保持浏览器数据目录。

#### Scenario: Engine startup
- **WHEN** ScraperEngine.start() 被调用
- **THEN** 系统启动 Chromium 浏览器（persistent context），注入 playwright-stealth 反检测脚本，加载已保存的 Cookie

#### Scenario: Engine shutdown
- **WHEN** ScraperEngine.stop() 被调用
- **THEN** 系统保存当前 Cookie 到 sessions 表，关闭所有页面和浏览器

#### Scenario: Page reuse
- **WHEN** 调用 get_page() 获取可用页面
- **THEN** 复用已有空闲 tab 或创建新 tab，返回 Page 对象

### Requirement: Cookie persistence
系统 SHALL 将浏览器 Cookie 保存到 SQLite sessions 表，支持跨重启恢复登录态。

#### Scenario: Save cookies
- **WHEN** 调用 save_cookies(name) 时
- **THEN** 将当前浏览器所有 Cookie 序列化为 JSON 存储到 sessions 表

#### Scenario: Load cookies
- **WHEN** 调用 load_cookies(name) 时
- **THEN** 从 sessions 表读取 Cookie 并注入到浏览器 context 中

### Requirement: QR code login
系统 SHALL 支持抖音二维码扫码登录流程。

#### Scenario: Login flow
- **WHEN** 检测到未登录状态
- **THEN** 导航到 douyin.com，展示二维码页面，等待用户扫码，扫码成功后自动保存 Cookie

#### Scenario: Login status check
- **WHEN** 调用 check_login()
- **THEN** 通过检查 Cookie 或导航用户页面判断是否已登录，返回布尔值

### Requirement: Anti-detection
系统 SHALL 使用 playwright-stealth 隐藏浏览器自动化特征。

#### Scenario: Webdriver flag hidden
- **WHEN** 浏览器启动后
- **THEN** navigator.webdriver 返回 false，Chrome 版本号为真实版本，无 CDP 调用栈泄露

### Requirement: API response interception
系统 SHALL 使用 page.route() 拦截 `/aweme/v1/web/**` 的 API 响应。

#### Scenario: Intercept API response
- **WHEN** 浏览器发出匹配 `/aweme/v1/web/**` 的请求
- **THEN** 拦截器放行请求、捕获响应 JSON 数据、存入队列，然后将原始响应返回给页面

#### Scenario: Wait for specific API
- **WHEN** 调用 wait_for(pattern, timeout) 等待特定 API 响应
- **THEN** 在 timeout 内返回匹配 pattern 的 API 响应数据，超时则抛出异常
