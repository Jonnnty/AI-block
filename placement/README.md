# 场景编辑器（placement）

拖入 Gaussian Splat 模型（PLY）进行摆放，编辑相机轨迹，导出 JSON 配置。

## 模型从哪来

1. **AI 生图**：生成目标物品的图像，背景尽量 **纯白**，物体完整、少重叠。
2. **SAM 3D Objects → PLY**：使用 [facebookresearch/sam-3d-objects](https://github.com/facebookresearch/sam-3d-objects) 做单物体/多物体 3D 重建，导出 Gaussian Splat：

   ```python
   output = inference(image, mask, seed=42)
   output["gs"].save_ply("model.ply")
   ```

3. **拖入本编辑器**：在线或本地打开场景编辑器，导入 `.ply` 文件。

### Kimodo 动作人模（NPZ）

1. 用 [Kimodo](https://github.com/nv-tlabs/kimodo) 生成 `motion.npz`（77 关节 SOMA）。
2. 在编辑器 **模型** 页点击「选择 PLY / NPZ 文件」，或拖入 `.npz`。
3. 导入后显示**素色 SOMA 人模**（非骨骼线框）；可用 Q/W 移动旋转，与 PLY 场景一起摆放。
4. **4D 渲染**：在 **相机** 页编辑轨迹后，「预览路径视频 / 导出 PNG 序列」会按时间同步人模动作与相机运动。

首次加载需下载 `vendor/soma_skin.bin`（约 1.3MB）。

## 在线

https://jonnnty.github.io/AI-block/placement/placement_editor.html

## 本地

```cmd
pip install -r requirements.txt
python serve_editor.py
```

→ http://127.0.0.1:8080/placement_editor.html

或双击 `start_editor.bat`。
