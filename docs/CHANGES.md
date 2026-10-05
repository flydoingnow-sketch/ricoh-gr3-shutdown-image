# 如何在原项目上适配 GR III

上游：[radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion](https://github.com/radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion)，分析基准提交 `0f1239202e8d15de9281a065a807c4f9b4727104`。

本项目参考其固件分析方法、工厂入口和 GR IIIx Urban 分步脚本，不宣称独立发明底层机制。

| 方面 | 原工程参考 | 本次改动 |
|---|---|---|
| 机型范围 | GR IV 系列、IIIx Urban 等分别研究 | 只绑定普通 GR III 2.10，其他型号拒绝 |
| 工厂入口 | 上游入口生成方法 | 从 GR III 2.10 ARM 格式化路径和常量重新推导 00078350.588，并在机身验证 |
| 资源路径 | IIIx Urban 使用 GB_Urban.jpg | 本机双导出验证 GoodBye.jpg，不直接沿用 Urban 资源 |
| 原图长度 | Urban 的107902字节 | 绑定普通 GR III 的7264字节、完整原图哈希、720×480及JPEG结构 |
| 编码 | 上游单扫描等长 JPEG 思路 | 独立有界搜索，保留 DC，拒绝过粗色度，显示最终 JPEG，不靠填充凑长度 |
| 写入 | 上游 Script 类、分步备份及复制 | 新建机内备份和临时文件；按42字节分段写入；完整重建载荷；检查行长和前向跳转 |
| 文件名 | 固定实验名称 | 每次操作包生成独立四位十六进制标识，机内/卡上已存在则停止 |
| 恢复 | 上游备份复制恢复 | 每个操作包附 recovery，恢复该次修改前图片；不能误称所有包均恢复最初理光图 |
| 普通用户流程 | 命令行及研究报告 | 新增 Tk 桌面界面、CLI、源代码启动器、应用打包和自动构建配置 |
| 证据 | 各机型分别记录 | 本次物理读回、静态分析、主机模型分开列，不把新封装标成已实测 |

## 文件来源

`tools/vendor/gr3x_urban_shutdown.py` 和 `tools/vendor/gr3x_urban_jpeg.py` 保留上游源码，不修改内容，并保留 LICENSE、NOTICE。工作流通过调用 Script 类设置 GR III 的大小和路径。

`tools/jpeg_profile.py` 为本次 JPEG 严格格式检查的派生文件；桌面工具使用 `tools/gr3_workflow.py` 的修正版编码逻辑。`tools/firmware_analysis.py` 由本次样本解包/分析脚本整理而来，提供固件格式检查，不要求普通用户每次操作都重新解包固件。

`tools/gr3_workflow.py`、`app.py`、`cli.py`、`tests/test_gr3_workflow.py` 和本项目文档新增。组合包是新包装路径，尚未整套实机验证。

## 公开仓库与私人操作包的区别

公开仓库只包含代码、文档、许可和测试，实际图片由用户在电脑本地选择。此前测试使用过的哈苏、麦当劳和理光原图不纳入公开仓库。生成的 TTL 内含用户 JPEG 字节，因此操作包也是用户素材的一份副本，不应随意推送到 GitHub。
