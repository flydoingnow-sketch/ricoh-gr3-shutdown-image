# 来源与许可

本项目参考并派生自：

- [radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion](https://github.com/radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion)
- 分析基准提交：[0f1239202e8d15de9281a065a807c4f9b4727104](https://github.com/radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion/tree/0f1239202e8d15de9281a065a807c4f9b4727104)
- TTL 构建器和 JPEG 解析参考：上游 `tools/gr3x_urban_shutdown.py`、`tools/gr3x_urban_jpeg.py`，以及工厂入口/固件分析工具和对应报告。
- 固件帧格式分析参考：[yeahnope/gr_unpack](https://github.com/yeahnope/gr_unpack)。本次有界解码器独立实现，未复制其代码。

`tools/vendor` 原样保留上游文件与 LICENSE、NOTICE；本次修改和新增文件在 CHANGES 中逐一标记。新增适配代码和文档按本仓库 LICENSE 非商业条款分发；不放宽第三方的许可。

上游当前采用 **GR IV Project Noncommercial Source License 1.0**。其新授权内容只能非商业使用、修改和再分发，不属于 OSI 定义的开源许可证。上游提及历史 Apache-2.0 授权仍然有效，但本发布不依赖尚未逐文件确认的历史授权去放宽整包权限。

非商业学习、研究和不收费分享可按许可证进行。收费安装、付费服务、带广告/联盟/订阅等营利活动不能自动套用非商业许可。如准备把相关材料用于商业宣传或变现，需向相应权利人取得书面许可。

不发布理光官方固件、提取的系统资源、用户机身读回或哈苏/麦当劳品牌图稿。图形界面让用户自行选择素材；生成的脚本包含图片字节，属于私人操作文件。商标与素材权利归各权利人，本项目没有官方合作或背书。

对外引用建议：

> 底层思路与 TTL 工具参考 radium-wang/ricoh-gr4-firmware-analysis-and-feature-expansion；本项目完成普通 GR III 2.10 的路径、原图格式验证与桌面流程适配。源码按原项目适用的非商业许可公开。
