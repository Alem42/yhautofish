# YiHuan AutoFish

异环自动钓鱼辅助脚本。

## 运行

打包后的版本直接运行：

```text
dist/FishAutoPython/FishAutoPython.exe
```

进入钓鱼点后按 `F10` 开始，按 `F12` 停止。

程序需要管理员权限，打包出的 exe 已带管理员权限 manifest。

## 分发

把整个目录压缩后发给别人，不要只发单独 exe：

```text
dist/FishAutoPython/
  FishAutoPython.exe
  _internal/
```

EasyOCR 模型已经随包放在：

```text
dist/FishAutoPython/_internal/models/easyocr/
  craft_mlt_25k.pth
  zh_sim_g2.pth
```

对方不需要安装 Python、`.venv`、PyTorch 或 EasyOCR，也不需要手动下载模型。

## OCR 自检

可以用下面的命令确认 exe 能加载 CPU 版 Torch 和随包模型：

```bat
dist\FishAutoPython\FishAutoPython.exe --ocr-self-test
```

自检结果会写入 `logs/autofish.log`。看到类似下面的内容就说明 OCR 环境正常：

```text
torch=2.11.0+cpu cuda_available=False
easyocr_reader_device=cpu
```

## 重新打包

本机已经有模型时，直接运行：

```bat
make_python_exe.bat
```

打包脚本会优先使用项目内的模型：

```text
models/easyocr/
  craft_mlt_25k.pth
  zh_sim_g2.pth
```

如果项目内没有模型，但当前用户目录存在 EasyOCR 缓存，脚本会自动从这里复制：

```text
C:\Users\用户名\.EasyOCR\model\
```

## 文件说明

- `autofish.py`: 主程序入口，负责窗口控制、OCR 线程、自动钓鱼流程和钓鱼条控制。
- `config.py`: 静态配置，包含 OCR 文本、区域、时间参数、坐标、按键和颜色阈值。
- `ocr_utils.py`: OCR 预处理、文本规范化、关键词识别和区域读取。
- `FishAutoPython.spec`: PyInstaller 打包配置，包含 CPU Torch、EasyOCR 模型和 VC runtime 处理。
- `requirements.txt`: CPU 版依赖列表。
- `make_python_exe.bat`: 一键安装依赖并生成 onedir 发布目录。
