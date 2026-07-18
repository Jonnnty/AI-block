# AI-block

AI 场景创建和视频生成（持续扩展中）。

## 模块

| 模块 | 说明 | 在线链接 |
|------|------|----------|
| **placement** | Gaussian Splat 模型摆放 + 相机轨迹 | [打开摆放器](https://jonnnty.github.io/AI-block/placement/placement_editor.html) |

## 在线使用

直接打开链接即可，无需安装、无需 GitHub 配置：

https://jonnnty.github.io/AI-block/placement/placement_editor.html

导入 PLY 模型、摆放、编辑相机轨迹；配置可用浏览器 **保存 / 导入 / 导出 JSON**。

## 模型生成

摆放器使用的是 **3D Gaussian Splat** 模型（`.ply`）。可按下面流程自己生成：

1. **AI 生图**：用任意 AI 绘图工具生成想要的物品，尽量放在 **纯白背景** 上，主体清晰、少遮挡。
2. **转 3D 高斯**：用 Meta 的 [SAM 3D Objects](https://github.com/facebookresearch/sam-3d-objects) 从图片（及 mask）重建 3D，并导出 PLY：

   ```python
   output = inference(image, mask, seed=42)
   output["gs"].save_ply("model.ply")
   ```

   详见仓库 README 与 `demo.py` / notebook。

3. **导入摆放器**：把生成的 `.ply` 拖入 [摆放器](https://jonnnty.github.io/AI-block/placement/placement_editor.html) 即可摆放。

## 本地开发

```cmd
cd placement
pip install -r requirements.txt
python serve_editor.py
```

## 维护者：部署说明

以下内容**仅仓库维护者**需要看；普通用户不用管。

推送 `main` 后 Actions 自动部署。若 fork 本仓库或新建站点，**首次**需在 **Settings → Pages → Source** 选 **GitHub Actions**，再 Re-run 部署 workflow。
