# Nowledge Mem Tools
- 脚本由 Opus 4.5 模型生成
- 用于 [Nowledge Mem](https://nowledge.com)
- 目前仅支持将 ChatWise 应用的对话记录导入到 Nowledge Mem 的 Threads，随缘更新适配其他 app 。

## ✨ 功能特性

- 📦 支持 ZIP 压缩包或解压目录作为输入
- 🔍 自动检测导出格式
- 🚫 智能去重，避免重复导入
- 📊 美观的终端输出界面

## 📸 截图预览

### 自动模式
批量导入所有记录，适合大量数据快速导入：

![自动模式](screenshot/automatic%20mode.png)

### 手动模式
逐条确认导入，可预览每条记录详情：

![手动模式](screenshot/manual%20mode.png)

## 🚀 安装

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/nowledge-mem-tools.git
cd nowledge-mem-tools

# 安装依赖
pip install -r requirements.txt
```

## 📖 使用方法

### ChatWise 导入

```bash
# 基本用法（交互式选择模式）
python chatwise_to_nowledge.py <zip文件或解压目录>

# 自动模式 - 批量导入所有记录
python chatwise_to_nowledge.py <路径> --auto

# 手动模式 - 逐个确认导入
python chatwise_to_nowledge.py <路径> --manual
```

### 示例

```bash
# 使用 ZIP 文件
python chatwise_to_nowledge.py chatwise-export-2025-01-01.zip --auto

# 使用解压后的目录
python chatwise_to_nowledge.py ./chatwise-export/ --manual
```

## 📋 支持的导入源

| 应用 | 状态 | 说明 |
|------|------|------|
| ChatWise | ✅ 已支持 | 支持 ChatWise 导出的 ZIP 文件 |
| 更多应用 | 🔜 随缘更新 |

## ⚙️ 配置

确保 Nowledge Mem 服务正在运行，默认 API 地址为：

```
http://127.0.0.1:14242
```
