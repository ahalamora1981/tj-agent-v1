---
name: file-organizer
description: 帮助用户整理文件和文件夹，按照类型、日期或其他规则进行分类。
triggers:
  - 整理文件
  - 整理文件夹
  - 分类文件
  - organize files
---

# File Organizer Skill 指令

当用户要求整理文件或文件夹时，请严格按照以下步骤执行：

## 步骤 1：了解当前目录结构
使用 `list_directory` 工具查看当前目录的文件和文件夹。

## 步骤 2：分析文件类型
统计各类文件的数量：
- 文档文件：.txt, .doc, .docx, .pdf, .md
- 代码文件：.py, .js, .ts, .java, .cpp, .go
- 图片文件：.jpg, .png, .gif, .svg
- 压缩文件：.zip, .tar, .gz, .rar
- 其他

## 步骤 3：创建分类文件夹
根据分析结果，创建合适的分类文件夹：
- `documents/` - 文档
- `code/` - 代码
- `images/` - 图片
- `archives/` - 压缩文件
- `others/` - 其他

## 步骤 4：移动文件
使用 `bash` 命令配合 `mv` 将文件移动到对应文件夹。

## 步骤 5：输出整理报告
向用户报告整理结果，包括：
- 分类统计
- 创建的文件夹
- 移动的文件列表
