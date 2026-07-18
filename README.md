# AI-block

AI 相关工具集合（持续扩展中）。

## 模块

| 模块 | 说明 | 在线链接 |
|------|------|----------|
| **placement** | Gaussian Splat 模型摆放 + 相机轨迹 | [打开摆放器](https://jonnnty.github.io/AI-block/placement/placement_editor.html) |

## 在线使用

直接打开链接即可，无需安装、无需 GitHub 配置：

https://jonnnty.github.io/AI-block/placement/placement_editor.html

导入 PLY 模型、摆放、编辑相机轨迹；配置可用浏览器 **保存 / 导入 / 导出 JSON**。

## 本地开发

```cmd
cd placement
pip install -r requirements.txt
python serve_editor.py
```

## 维护者：部署说明

以下内容**仅仓库维护者**需要看；普通用户不用管。

推送 `main` 后 Actions 自动部署。若 fork 本仓库或新建站点，**首次**需在 **Settings → Pages → Source** 选 **GitHub Actions**，再 Re-run 部署 workflow。
