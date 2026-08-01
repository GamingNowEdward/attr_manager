# Attribute Manager - Maya Style

这是 `attributeManager` 的独立 Maya 风格版本，使用更接近 Channel Box 的灰色层级、`#5285a6` 选中高亮与紧凑控件。原版项目未被修改。

在 Maya Script Editor 中启动：

```python
import sys; sys.path.insert(0, r"C:\\opencode")
import attributeManager_maya; attributeManager_maya.launch()
```

# Attribute Manager

Maya 2024/2025 属性集合面板工具。将场景中常用属性聚合到一个可停靠面板，支持快速调节、分组管理、拖拽排序，配置随场景保存。

## 功能

- 从 Channel Box 或手动输入添加属性（自动搜索 Shape 节点）
- "+ Last Attr" 快捷按钮：自动读取最近一次修改的属性（面板修改或 Script Editor 日志）
- 属性按类型自动匹配控件：Slider+SpinBox / CheckBox / ComboBox / 色块按钮
- 显示类型可选：Auto / Number / Color，颜色属性点击打开 Maya 色板
- 自定义 Slider 范围：右键滑块 → Set Min/Max/Range/Reset（范围围绕当前值自动生成）
- 全局 Int/Float Snap 切换：整数步进 / 浮点步进（3 位小数）
- 分组管理：折叠、重命名（双击）、拖拽排序
- 属性条目：拖拽排序、跨组拖拽、双击重命名；空分组显示占位提示，仍可作为拖放目标
- 完整撤销支持：属性修改（含滑块拖动）均可撤销，配置保存不污染撤销栈
- 撤销/重做同步：Ctrl+Z / Ctrl+Shift+Z 后面板数值自动刷新
- 配置持久化：存储在场景内 `attrManager` network 节点，随文件保存
- 节点重命名后通过 UUID 自动恢复引用
- 高性能：配置保存 300ms 防抖；滑块拖动合并为单个撤销步骤

## 安装

将 `attributeManager` 文件夹的**父目录**加入 Maya Python 路径：

**方式一：Maya.env（推荐）**
```
MAYA_SCRIPT_PATH += C:/opencode
```
文件位置：`~/Documents/maya/2024/Maya.env`

**方式二：手动**
```python
import sys
sys.path.insert(0, r"C:\opencode")
```

## 使用

```python
import attributeManager
attributeManager.launch()
```

面板会停靠到 Maya 右侧。`launch()` 每次调用会自动热重载所有模块，方便开发迭代。

## 环境要求

- Maya 2024 / 2025（Python 3 + PySide6）
- 兼容 Maya 2022/2023（PySide2 fallback）

## 项目结构

```
attributeManager/
├── attributeManager.py      # 入口
├── __init__.py              # 包导出（launch/reload_modules）
├── core/
│   ├── attr_data.py         # 数据模型 + JSON 序列化
│   ├── scene_io.py          # 场景节点读写
│   └── channel_box.py       # Channel Box 查询 + Last Attr
└── ui/
    ├── main_window.py       # Dockable 主窗口
    ├── group_section.py     # 分组 + 拖拽
    ├── attr_row_widget.py   # 属性行控件
    ├── add_attr_dialog.py   # 添加属性对话框
    └── styles.py            # QSS 样式表
```
