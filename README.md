# Ricoh GR III 2.10 关机图片工具

把自己的图案放到普通 **GR III / Ver.2.10 的关机显示画面**。电脑工具负责图片排版、等长 JPEG 编码、TTL 操作包生成和读回校验。相机仍需要用存储卡运行脚本。

本项目是 GR III 的独立适配，参考 [radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion](https://github.com/radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion)，不是理光官方软件。当前基于上游非商业源码许可证公开源码，不能称为 OSI 认可的开源项目。详见 [LICENSE](LICENSE)、[NOTICE](NOTICE) 和 [来源与许可](docs/ATTRIBUTION.md)。

## 先看兼容范围

| 项目 | 当前状态 |
|---|---|
| 普通 GR III / Ver.2.10 | 一台机身已验证工厂入口、原图导出、分步哈苏替换和正常显示 |
| 第一版麦当劳资源 | 机内最终读回匹配，用户反馈画质问题；不是所有版本显示均通过 |
| 缩小上移修正版 | 桌面最终 JPEG 已检查，最终相机显示尚待反馈 |
| 本仓库桌面工具、随机文件名、一次开机组合包 | 电脑测试通过，包装后的整套流程未实机资格验证 |
| GR III 1.91、GR IIIx、GR IV、特殊版本 | 不支持，不生成跨机型操作包 |
| 其他 GR III 2.10 机身 | 必须先导出并完整匹配本项目原图哈希；单机结果不构成普遍兼容承诺 |

**这修改的是 `GoodBye.jpg` 关机资源。拍摄界面、张数、相机版本、品牌、画质和摄影功能不会随图案变更。** 不分发官方固件、机内原图、用户读回或品牌图稿。

## 普通人怎么用

推荐下载适合电脑的 `GR3ImageTool` 应用。首次发布提供 Apple Silicon Mac 的本地构建；Windows / Intel Mac 需对应构建，不能把 arm64 Mac 包复制过去使用。应用不是已公证的 Apple 官方软件。

1. 在相机菜单确认型号为普通 GR III、版本为 2.10；照片先备份，准备电量充足的电池、存储卡、读卡器和自己的图案。
2. 工具“生成原图导出包”。把生成目录的 `card` **内部文件**复制到卡根目录。
3. 按住 MENU 开机，只开启 `Script Enable`；关机后正常开机一次。读写结束再关机，取得 `G3READ1.JPG`、`G3READ2.JPG`。
4. 把两份原图保存到电脑，工具“校验原图”。它们须完整一致，并匹配普通 GR III 2.10 的已知原图。
5. 选择自己的图片、背景色，并保留“缩小上移”选项。编码后检查工具显示的**实际 JPEG**，不要只看未压缩预览。
6. 默认走分步流程：生成临时导入包 → 相机运行 → 校验读回并生成写入包 → 相机运行 → 校验最终读回。
7. 移走 `script/startup.ttl`，再按 MENU 开机关闭 `Script Enable`。正常开关机确认后移走入口文件和日志；原图及操作包留在电脑。

完整操作见 [安装与恢复教程](docs/INSTALL.md)。

## 能否做成一个文件

可以把电脑工具打成一个 `.app` 或 `.exe`，用户不用安装 Python，也不用写脚本。图形界面已经实现选择图片和自动生成操作包。

**首次仍要备份原图，相机端仍需开启脚本并开机运行。** 本项目不提供未经验证的 USB 直刷接口，也不把普通 JPEG 当作官方固件安装。

一次开机组合包是实验选项：省掉中间电脑读回校验，不能把“检查文件大小”当作“机内完整哈希校验”。最终仍应核对电脑读回。公共版本默认保留分步流程。

## 从源码运行

Python 3.10+，带 Tk 的 Python，以及 Pillow。Mac 可以运行 `启动工具.command`；Windows 可以运行 `start-windows.bat`。首次会创建本地虚拟环境和安装依赖。Linux 可使用 CLI，图形界面需系统 Tk 支持。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tools/app.py
```

CLI 示例，输出为新建的电脑本地目录，不能直接指定存储卡：

```sh
python tools/cli.py export ./packages/export
python tools/cli.py check-original ./private/original
python tools/cli.py encode ./private/original ./private/my-art.png ./packages/candidate --background '#151515'
python tools/cli.py stage ./private/original ./packages/candidate ./packages/stage
python tools/cli.py install ./packages/stage ./private/stage-readbacks ./packages/install
python tools/cli.py verify ./packages/install ./private/final-readbacks
```

## 工程资料

- [原理与固件分析](docs/PRINCIPLE.md)：为什么能实现，入口、盘符、JPEG 与计数栏关系。
- [相对原项目的改动](docs/CHANGES.md)：机型路径、7264 字节格式、脚本写入、恢复和桌面封装。
- [验证记录及边界](docs/VALIDATION.md)：静态分析、实机观察、电脑测试分别记录。
- [开发与发布](docs/DEVELOPMENT.md)：测试、打包、GitHub 发布。
- [来源、许可与素材](docs/ATTRIBUTION.md)：上游引用和非商业约束。

```sh
python -m unittest discover -s tests -v
python tools/app.py --self-test
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --windowed --name GR3ImageTool --paths tools/vendor --hidden-import gr3x_urban_jpeg --add-data 'LICENSE:.' --add-data 'NOTICE:.' tools/app.py
```

源码不附带相机固件和品牌图片。请使用自己有权使用的图稿。相机内部资源修改可能失败，始终保留原图与当前图片备份；异常时保留日志，不清空或反复执行。这个工具不支持修改校准项，也不支持保证恢复或保修结果。
