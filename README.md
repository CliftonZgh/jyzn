# 安心就医指南

一个基于 MkDocs Material 的中文就医指南，可部署到 Cloudflare Pages。

## 本地预览

```bash
uv venv
uv pip install -r requirements.txt
uv run mkdocs serve
```

打开 `http://127.0.0.1:8000`。

## 构建

```bash
python scripts/build_guide_package.py \
  --source content/example-guide-package.json \
  --output docs/guides/example
uv run mkdocs build --strict
```

生成的静态文件位于 `site/`。

示例指南包的三个患者视图都由同一份结构化底稿生成。生成命令会先严格检查
院区身份、安全说明和每个信息项的必填核验字段；检查失败时不会写出患者页面。

## 部署到 Cloudflare Pages

### 方式一：连接 Git 仓库（推荐）

1. 将本项目推送到 GitHub 或 GitLab。
2. 在 Cloudflare 控制台进入 **Workers & Pages → Create → Pages → Connect to Git**。
3. 填写构建设置：
   - Framework preset：`MkDocs`
   - Build command：`pip install -r requirements.txt && python scripts/build_guide_package.py --source content/example-guide-package.json --output docs/guides/example && mkdocs build --strict`
   - Build output directory：`site`
   - Environment variable：`PYTHON_VERSION` = `3.12`
4. 保存并部署。以后每次推送都会自动重新构建。

### 方式二：命令行直接部署

先从结构化底稿重新生成全部视图并严格构建，再登录并发布：

```bash
npm run build
npx wrangler login
npm run deploy
```

生产站点地址为 <https://medical-guide.pages.dev/>。如果以后绑定自定义域名，请同步更新
`mkdocs.yml` 中的 `site_url`。

## 当前可交付成果

- 通用中文就医行动指南；
- 广州市妇女儿童医疗中心珠江新城院区普通门诊到院指南（有限覆盖首版）；
- 从结构化底稿派生手机、速查、打印、示意图和二维码视图的发布流水线；
- 18 项自动化发布门禁测试。
