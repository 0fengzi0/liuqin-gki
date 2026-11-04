# liuqin-gki-builder

Xiaomi Pad 6 Pro（liuqin）原厂 GKI 内核的可重复构建管线。

设备当前运行 `5.10.236-android12-9-00003-gfb24cf99ad97-ab14313284`，即
Android common kernel `android12-5.10` 分支上的
[`fb24cf99ad97`](https://android.googlesource.com/kernel/common/+/fb24cf99ad973cd4c7c7fa375c6053f939ef3a89)
提交。本仓库从**同一提交**、用**同一版 Clang（r416183b）**、以**设备实机导出的
配置**重建 GKI 内核，并用设备上全部 353 个厂商模块的符号 CRC 基线做 KMI
兼容验收，最后按原厂 boot 头参数打包 `boot.img`。

厂商模块、vendor_boot、设备树、KernelSU 均保留设备现有内容，不重建。

## 仓库内容

| 路径 | 说明 |
| --- | --- |
| `config/running.config` | 设备 `/proc/config.gz` 导出的完整内核配置（SHA-256 `aa19d5a2…`） |
| `baseline/symbol-crcs.json` | 353 个厂商模块导入符号 CRC 基线（3624 个符号，0 冲突），由 `.ko` 的 `__versions` 提取 |
| `packaging/ramdisk-current.cpio.lz4` | 当前槽位 boot 的通用 ramdisk（含 KernelSU LKM），原样复用 |
| `scripts/check-kmi.py` | `Module.symvers` 对比基线的验收脚本 |
| `.github/workflows/build-gki.yml` | 手动触发的构建工作流 |

## 使用

Actions → **build-gki** → Run workflow。`lto` 输入默认 `thin`。

- `thin`：推荐。实机配置固定 Full LTO，但 Full LTO + KASAN + CFI 的 vmlinux
  链接普遍超出免费 runner 的 16 GB 内存；ThinLTO 不改变符号 CRC（CRC 来自
  类型签名），不影响 KMI 契约。此为**有意记录的偏差**。
- `full`：复现原厂二进制形态，需要内存更大的 runner，否则大概率 OOM。

产物：`boot-new.img`、`Image`、`Module.symvers`、`.config`、配置漂移报告、
`kmi-report.json`、构建日志。**KMI 报告出现 mismatch/missing 即为失败**，
该内核不应刷入设备。

## 兼容性模型

设备内核 `CONFIG_MODVERSIONS=y` 时，内核校验模块 vermagic 会忽略版本号
前缀（`same_magic()` 只比较 flags 段），因此：

1. 模块能否加载取决于 `__versions` 中的符号 CRC 与新内核 `Module.symvers`
   是否一致 —— 本仓库的基线就是全部已加载模块的这份期望；
2. `kernelsu.ko`（5.10.252-dirty 构建）没有任何版本化导入，仅要求 199 个
   未版本化符号存在，同源重建内核天然满足；
3. boot 头参数取自原机：header v4、os_version 12.0.0、patch level 2025-09、
   cmdline 为空；原机 boot_signature（VTS 测试签名）不写入 —— 设备已解锁
   （orange 状态），AVB 不校验该字段。

## 刷入与回退（摘要）

首次验证建议：`fastboot boot boot-new.img` 临时引导（小米部分机型禁用）；
不可用则刷入**非当前槽位**（如当前 `_a` 则 `fastboot flash boot_b boot-new.img`
+ `fastboot set_active b`），回退时刷回原始镜像并 `set_active a`。刷写前
确认手中保留原厂 boot 备份。

## 许可说明

内核配置与 `Module.symvers` 来源于 GPL-2.0 内核产物；ramdisk 为 Apache-2.0
Android 通用组件。基线 JSON 只含符号名与 CRC 数值，不含任何二进制。

## 来源与依据

- ACK 提交与构建元数据核对：小米 Pad 6 Pro 实机基线记录（项目主仓库
  `tools/liuqin/DEVICE-BASELINE-2026-11-04.md`）
- 模块 CRC 基线由
  [`Xiaomi_Kernel_OpenSource` 主仓库](https://github.com/MiCode/Xiaomi_Kernel_OpenSource)
  的 `tools/liuqin/extract-module-crcs.py` 从设备模块提取（该脚本已对人工
  逐字节核对的 7 模块基线 100% 复现）
- Clang 下载地址与 SHA-256 取自 `build.config.common` 指定的
  `master-kernel-build-2021` 预编译版本
