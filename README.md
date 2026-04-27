# YiHuan AutoFish

Windows 自动钓鱼辅助脚本。脚本会按窗口标题查找游戏窗口，激活窗口后根据游戏客户区尺寸换算点击坐标，并循环执行按键/点击流程。

## 使用方式

1. 打开游戏并保持目标窗口标题包含 `异环`。
2. 运行 `dist/YhFishAuto0.0.1.exe` 
3. （可能）同意管理员权限弹窗。
4. 亲自前往钓鱼点并点击开始钓鱼，进入这个页面
![alt text](image.png)
5. 按 `F10` 开始，按 `F12` 停止。


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

