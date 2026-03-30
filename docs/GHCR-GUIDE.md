# GitHub Container Registry 使用指南

本文档说明如何使用 GitHub Container Registry (ghcr.io) 构建和推送 Docker 镜像。

## 自动构建（推荐）

项目已配置 GitHub Actions 自动构建工作流，推送到 main/master 分支或创建 tag 时会自动构建并推送镜像。

### 触发条件

- 推送到 `main` 或 `master` 分支
- 创建 `v*` 格式的 tag（如 `v1.0.0`）
- 手动触发工作流

### 镜像标签规则

| 触发条件 | 镜像标签示例 |
|---------|-------------|
| main 分支推送 | `ghcr.io/baiyz0825/titok-crawl:main`, `ghcr.io/baiyz0825/titok-crawl:latest` |
| v1.2.3 tag | `ghcr.io/baiyz0825/titok-crawl:1.2.3`, `ghcr.io/baiyz0825/titok-crawl:1.2`, `ghcr.io/baiyz0825/titok-crawl:1` |
| PR #123 | `ghcr.io/baiyz0825/titok-crawl:pr-123` |

## 手动推送镜像

### 1. 创建 Personal Access Token

1. 访问 https://github.com/settings/tokens/new
2. 选择以下权限：
   - `write:packages` - 推送镜像
   - `read:packages` - 拉取镜像
   - `delete:packages` - 删除镜像（可选）
3. 生成并保存 token

### 2. 登录到 GitHub Container Registry

```bash
# 设置 token 环境变量
export CR_PAT=YOUR_TOKEN

# 登录
echo $CR_PAT | docker login ghcr.io -u baiyz0825 --password-stdin
```

### 3. 构建镜像

```bash
# 本地构建
docker build -t ghcr.io/baiyz0825/titok-crawl:latest .

# 或使用构建脚本
./build.sh
```

### 4. 标记镜像

```bash
# 标记为 latest
docker tag douyin-scraper:latest ghcr.io/baiyz0825/titok-crawl:latest

# 标记为特定版本
docker tag douyin-scraper:latest ghcr.io/baiyz0825/titok-crawl:1.0.0
```

### 5. 推送镜像

```bash
# 推送 latest
docker push ghcr.io/baiyz0825/titok-crawl:latest

# 推送特定版本
docker push ghcr.io/baiyz0825/titok-crawl:1.0.0
```

## 拉取镜像

### 公开镜像（无需登录）

```bash
docker pull ghcr.io/baiyz0825/titok-crawl:latest
```

### 私有镜像（需要登录）

```bash
# 登录
echo $CR_PAT | docker login ghcr.io -u baiyz0825 --password-stdin

# 拉取
docker pull ghcr.io/baiyz0825/titok-crawl:latest
```

## 使用拉取的镜像

### docker-compose.yml

```yaml
services:
  app:
    image: ghcr.io/baiyz0825/titok-crawl:latest
    container_name: douyin-scraper
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./data:/app/data
    environment:
      - HEADLESS=true
```

### 直接运行

```bash
docker run -d \
  -p 80:80 \
  -v $(pwd)/data:/app/data \
  -e HEADLESS=true \
  --name douyin-scraper \
  ghcr.io/baiyz0825/titok-crawl:latest
```

## 设置镜像可见性

1. 访问 https://github.com/baiyz0825?tab=packages
2. 点击 `titok-crawl` 包
3. 点击 "Package settings"
4. 在 "Danger Zone" 中更改可见性：
   - **Public** - 任何人可拉取
   - **Private** - 仅你和你授权的人可拉取

## 多架构支持

GitHub Actions 工作流已配置支持以下架构：
- `linux/amd64` - 标准 x86_64 服务器
- `linux/arm64` - ARM 服务器（如 Apple Silicon Mac, AWS Graviton）

Docker 会自动拉取适合你系统架构的镜像。

## 查看镜像信息

### 在 GitHub 网页

访问 https://github.com/baiyz0825/titok-crawl/pkgs/container/titok-crawl

### 使用命令行

```bash
# 查看镜像详情
docker inspect ghcr.io/baiyz0825/titok-crawl:latest

# 查看镜像 digest
docker pull ghcr.io/baiyz0825/titok-crawl:latest
# 输出中的 Digest: sha256:...
```

## 故障排查

### 登录失败

- 确认 token 有 `write:packages` 权限
- 确认用户名正确（小写）
- 确认 token 未过期

### 推送失败

- 确认已登录
- 确认有写入权限
- 检查镜像名称是否正确（小写）

### 拉取私有镜像失败

- 确认已登录
- 确认有读取权限
- 检查包的访问设置

## 相关链接

- [GitHub Container Registry 文档](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [GitHub Actions 工作流文件](../.github/workflows/docker-publish.yml)
- [Docker 镜像包页面](https://github.com/baiyz0825/titok-crawl/pkgs/container/titok-crawl)
