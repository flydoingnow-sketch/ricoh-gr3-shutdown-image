# 开发、打包与 GitHub 发布

## 目录

- `tools/app.py`：Tk 桌面界面，任务线程执行编码/检查，主线程展示最终 JPEG。
- `tools/cli.py`：同一工作流的命令行入口。
- `tools/gr3_workflow.py`：操作包、JPEG 编码、随机文件名、完整读回校验。
- `tools/jpeg_profile.py`：严格 JPEG 解析与已知原图约束。
- `tools/firmware_analysis.py`：离线固件解包与报告，不参与 USB 或相机写入。
- `tools/vendor`：上游依赖和许可证。
- `tests`：主机侧模型与拒绝条件测试。

输出包含图片和内嵌图片脚本，必须保存在 `private/`、`packages/` 或仓库外；不要提交。`.gitignore` 只是一层辅助，不代替发布前文件检查。

## 本地构建

```sh
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -v
python tools/app.py --self-test
python -m PyInstaller --noconfirm --windowed --name GR3ImageTool --paths tools/vendor --hidden-import gr3x_urban_jpeg --add-data 'LICENSE:.' --add-data 'NOTICE:.' tools/app.py
```

Mac 产物是 `dist/GR3ImageTool.app`；Windows 产物是 `dist/GR3ImageTool/` 中的应用及运行库，应整体打包。可另行试验 `--onefile` 生成独立 EXE，但须重新测试，不能只改文件扩展名。Mac `.app` 虽显示为单个应用，本质是文件包。

`.github/workflows/build.yml` 在 Mac 和 Windows 分别运行测试及打包，保存 Actions artifact。它目前不自动发布 Release，也不把未验证版本标为正式版。架构由 runner 决定；发布时注明 arm64/x86_64，不承诺 universal。

## 发布到 GitHub

仓库建议名：`ricoh-gr3-shutdown-image`，公开、独立适配仓库，保留上游链接。版本建议 `v0.1.0-preview`。

可使用 GitHub CLI：

```sh
gh auth login
# 在工程目录，已建立本地 Git 提交后运行：
gh repo create ricoh-gr3-shutdown-image --public --source . --remote origin --push
```

也可在网页创建空仓库，然后添加其真实 URL 为 origin 并 push。不要把 token 放在 URL、文档、截图或聊天里。

`publish_github.py` 是另一种本地发布入口：要求用户在终端输入 token（隐藏输入），或从本地环境变量读取；使用 GitHub API 创建公开仓库并推送当前提交。权限只需目标仓库创建/写入；没有凭据时无法代替用户登录。网络/认证失败不会宣称发布成功，也不会自动删除现有仓库。

发布前核对：公开文件只有源码、文档、许可与测试；不包含固件、读回、私人操作脚本、品牌图稿、绝对用户路径或认证信息。发布 README 写明非商业许可和未验证范围。

自媒体稿件在独立发布材料中，不默认推入源码仓库；仓库 URL 产生后再填写文案中的待填位置。
