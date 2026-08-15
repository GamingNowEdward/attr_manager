# Attribute Manager

Maya 2024.2 属性集合面板工具。将场景中常用属性聚合到一个可停靠面板，支持快速调节、分组管理、拖拽排序，配置随场景保存。

## 功能

- 从 Channel Box 或手动输入添加属性（自动搜索 Shape 节点）
- "+ Last Lock Attr" 快捷按钮：填充最近一次 **Lock 手势**对应的属性——在 Attribute Editor 中右键属性选择 **Lock** 即可记录（全局命令回调捕获 `setAttr -lock` 命令，不依赖 Script Editor）。属性保持锁定，仅在通过 Add 对话框实际添加时才自动解锁（不会干扰真实的锁定操作）
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
- 引用文件支持：被引用场景的 `attrManager` 配置以只读方式展示（分组、斜体行、禁止拖拽）；编辑引用属性时会在**原位创建覆写**——条目保持在原分组、显示 `override` 标记，点击 × 可移除覆写并恢复只读条目。创建/加载/卸载引用或导入文件时，面板会自动重新读取配置
- 主场景中指向引用节点的条目（如手动添加的 Translate Z）同样显示 `override` 标记
- 高性能：配置保存 300ms 防抖；滑块拖动合并为单个撤销步骤

## 测试

纯 Python 单元测试，覆盖数据模型、JSON 序列化与合并/保存往返逻辑（无需 Maya 或 PySide6）：

```bash
python -m unittest discover -s tests
```

## 快速开始

1. 下载并解压仓库
2. 双击 `copy_to_clipboard.bat` — 启动命令自动复制到剪贴板
3. 在 Maya Script Editor 中粘贴并执行

## 使用

或手动在 Maya Script Editor 中执行：

```python
__file__ = r"PATH_TO\launch.py"; exec(compile(open(__file__).read(), __file__, "exec"))
```

> **注意**：如果从 GitHub 下载 ZIP，解压后的文件夹名为 `attr_manager-main`。请相应调整路径。

面板会停靠到 Maya 右侧。每次调用会自动热重载所有模块，方便开发迭代。

## 环境要求

- Maya 2024.2（Python 3 + PySide6）
- **仅在 Maya 2024.2 上测试过，其他 Maya 版本未经测试，请自行测试**

## 项目结构

```
attributeManager_maya/
├── copy_to_clipboard.bat  # 自动生成启动命令
├── launch.py              # 便携式启动器
├── attributeManager.py    # 入口
├── __init__.py            # 包导出（launch/reload_modules）
├── core/
│   ├── attr_data.py       # 数据模型 + JSON 序列化
│   ├── merge.py           # 显示/保存合并变换（纯 Python）
│   ├── scene_io.py        # 场景节点读写
│   └── channel_box.py     # Channel Box 查询 + Last Lock Attr 钩子
├── tests/
│   ├── test_attr_data.py      # 序列化往返测试
│   └── test_merge_roundtrip.py # 合并/保存往返测试
└── ui/
    ├── main_window.py     # Dockable 主窗口
    ├── group_section.py   # 分组 + 拖拽
    ├── attr_row_widget.py # 属性行控件
    ├── add_attr_dialog.py # 添加属性对话框
    └── styles.py          # QSS 样式表
```
