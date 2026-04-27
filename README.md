# YiHuan AutoFish

Windows 自动钓鱼辅助脚本。脚本会按窗口标题查找游戏窗口，激活窗口后根据游戏客户区尺寸换算点击坐标，并循环执行按键/点击流程。

## 使用方式

1. 打开游戏并保持目标窗口标题包含 `异环`。
2. 运行 `dist/YhFishAuto0.0.1.exe` 或自己重新打包得到的 exe。
3. 同意管理员权限弹窗。
4. 按 `F10` 开始，按 `F12` 停止。

## 开发运行

```powershell
py -3.9 autofish.py
```

如果游戏以管理员权限运行，脚本也需要管理员权限运行。

## 坐标校准

双击运行：

```text
get_scaled_mouse_pos.bat
```

把鼠标移动到目标位置，读取输出里的 `ref=(x,y)`，然后填回 `autofish.py` 顶部的：

```python
LEFT_CLICK_REF_X = ...
LEFT_CLICK_REF_Y = ...
RIGHT_CLICK_REF_X = ...
RIGHT_CLICK_REF_Y = ...
```

## 打包 exe

双击运行：

```text
make_python_exe.bat
```

输出文件会生成到：

```text
dist/FishAutoPython.exe
```

## 版本管理建议

源码、脚本、README 提交到 GitHub；`build/`、`dist/`、`__pycache__/` 不提交。需要分发 exe 时，把 `dist` 里的 exe 上传到 GitHub Releases。
