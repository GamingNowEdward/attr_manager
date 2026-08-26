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
- 引用文件支持：被引用场景的 `attrManager` 配置以只读方式展示（组名/属性名带 `namespace:` 前缀、斜体行、禁止拖拽、禁止改名）；编辑引用属性时会在**原位创建覆写**——条目保持在原分组、显示 `override` 标记，点击 × 可移除覆写并恢复只读条目。创建/加载/卸载/移除引用或导入文件时，面板会自动重新读取配置；在 Reference Editor 中修改引用 namespace 不产生任何 Maya 事件，点击工具栏 Refresh 即可重读并更正前缀
- 主场景中指向引用节点的条目（如手动添加的 Translate Z）同样显示 `override` 标记

## 性能

- 配置保存 300ms 防抖；滑块拖动合并为单个撤销步骤
- Reference namespace 检测：创建/加载/卸载/移除引用及导入文件时由 MSceneMessage 事件驱动自动重新读取；Reference Editor 中修改引用 namespace 不产生任何 Maya 事件（`MNamespaceMessage` 不存在、`NameChanged` 不触发），需点击工具栏 Refresh 按钮重读场景配置（先落盘未保存修改再重读，前缀与引用组自动更正）
- 无后台轮询定时器：面板不做任何周期查询，播放动画与交互期间零额外开销

## 测试

测试套件运行在 Maya 自带的 `mayapy.exe` 中，直接驱动真实内核（场景读写、引用、命令钩子）：

```bash
"C:\Program Files\Autodesk\Maya2024\bin\mayapy.exe" -m unittest discover -s tests
```

覆盖范围与 headless 注意事项见 `tests/README.md`。

## 快速开始

1. 下载并解压仓库
2. 双击 `copy_to_clipboard.bat` — 启动命令自动复制到剪贴板
3. 在 Maya Script Editor 中粘贴并执行

## 使用

或手动在 Maya Script Editor 中执行：

```python
__file__ = r"PATH_TO\launch.py"; __name__ = "__main__"; exec(compile(open(__file__).read(), __file__, "exec"))
```

> **注意**：如果从 GitHub 下载 ZIP，解压后的文件夹名为 `attr_manager-main`。请相应调整路径。

面板会停靠到 Maya 右侧。每次调用会自动热重载所有模块，方便开发迭代。重启 Maya 后面板会自动恢复至原停靠位置（通过 workspace control 的 uiScript 机制）。

## 环境要求

- Maya 2024.2（Python 3 + PySide6）
- **仅在 Maya 2024.2 上测试过，其他 Maya 版本未经测试，请自行测试**

## 项目结构

```
attributeManager_maya/
├── copy_to_clipboard.bat  # 自动生成启动命令
├── launch.py              # 唯一入口（热重载 + 启动）
├── __init__.py            # 包导出（launch/reload_modules）
├── core/
│   ├── attr_data.py       # 数据模型 + JSON 序列化
│   ├── merge.py           # 显示/保存/节点收敛合并变换（纯 Python）
│   ├── scene_io.py        # 场景节点读写
│   └── channel_box.py     # Channel Box 查询 + Last Lock Attr 钩子
├── tests/
│   ├── support.py                   # 共享测试基座（场景隔离、引用夹具）
│   ├── test_attr_data.py            # 序列化 + resolve_entries
│   ├── test_merge.py                # 合并/保存行为矩阵
│   ├── test_scene_io.py             # 持久化 / 锁 / 撤销足迹
│   ├── test_channel_box.py          # setAttr 解析 + 命令钩子
│   └── test_reference_integration.py # 引用生命周期端到端
└── ui/
    ├── main_window.py     # Dockable 主窗口
    ├── group_section.py   # 分组 + 拖拽
    ├── attr_row_widget.py # 属性行控件
    ├── add_attr_dialog.py # 添加属性对话框
    └── styles.py          # QSS 样式表
```
