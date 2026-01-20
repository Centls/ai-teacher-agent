# 前端生产环境部署指南

Next.js 项目在生产环境通常有两种部署方式：**Node.js 服务器模式**（推荐）和 **静态导出模式**。鉴于本项目使用了 SSR (服务端渲染) 和 API 代理，必须使用 **Node.js 服务器模式**。

## 1. 准备工作

在服务器上，确保已安装：
- **Node.js** (v18+)
- **npm** (或 pnpm/yarn)
- **PM2** (进程守护工具，用于后台运行)

安装 PM2:
```bash
npm install -g pm2
```

## 2. 构建 (Build)

在项目根目录 (`frontend/`) 下执行：

```bash
# 1. 安装依赖 (如果还没装)
npm install

# 2. 构建生产版本
npm run build
```

构建成功后，会生成一个 `.next` 文件夹。

## 3. 启动 (Start)

### 方式 A: 直接启动 (测试用)
```bash
npm start
```
默认运行在 3000 端口。

### 方式 B: 使用 PM2 后台启动 (生产推荐)
创建一个 `ecosystem.config.js` 文件（可选，方便管理），或者直接运行：

```bash
pm2 start npm --name "ai-teacher-frontend" -- start
```

常用 PM2 命令：
- `pm2 list`: 查看运行状态
- `pm2 logs`: 查看日志
- `pm2 restart all`: 重启所有服务

## 4. 反向代理 (Nginx)

生产环境通常会在 Next.js 前面加一层 Nginx，用于配置域名、SSL 证书和 gzip 压缩。

**Nginx 配置示例 (`/etc/nginx/conf.d/ai-teacher.conf`):**

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 你的域名

    location / {
        proxy_pass http://localhost:3000;  # 转发给 Next.js
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

## 5. 环境变量

生产环境的环境变量通常配置在 `.env.production` 文件中，或者在 CI/CD 流水线中注入。
确保服务器上有 `.env.local` 或者 `.env.production`，并且包含：

```env
BACKEND_URL=https://api.your-domain.com/api/v1
```
(注意：生产环境的 API 地址通常是 HTTPS 的域名，而不是 localhost)
