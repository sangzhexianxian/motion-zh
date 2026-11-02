# motion-zh

**让英文视频模板在中文里不出错。**

一个很小的检查器，加一个已经跑通的示例模板。

> 给 AI 助手的一句话：
> **读取 https://github.com/sangzhexianxian/motion-zh 的 SKILL.md，用 `scripts/check_zh.py` 检查我这条中文文案能不能放进画面；放不下就告诉我改哪里，不要靠缩小字号硬塞。**

## 为什么有这个

`.motion` 模板几乎都是英文语境做的。它们的 `params.schema.json` 里写的是 `maxLength: 36`——对英文是 36 个字符，对中文大约是 **22 个字**，而实际画面里往往只放得下 **12 个字**。

结果就是：参数校验通过，出片一看，标题挤成三行、标点跑到行首、最后一个字孤零零挂在第二行。

这个仓库做三件事：

1. **算真账**：把英文 `maxLength` 折算成中文可读字数（系数 0.62），提前告诉你哪里会炸。
2. **查禁则**：中文标点不能出现在行首（`，。、；：？！）】》」』`），行尾不能是开括号。检查器有 Python 实现，模板里有 JS 对照实现，两边结果一致。
3. **给一个能抄的样板**：`templates/finance-cards/` 是一个把中文容量写进 schema 的完整 `.motion`，通过了 MotionGit 官方 `inspect`。

## 三种用法

```bash
# ① 审一个模板的中文适配度（别人的模板也能审）
python3 scripts/check_zh.py --schema path/to/params.schema.json --audit

# ② 校验一份参数放不放得下
python3 scripts/check_zh.py --params my.json --schema params.schema.json

# ③ 单条文案体检
python3 scripts/check_zh.py --text "降准落地，钱会流向哪三个方向" --chars 12 --lines 2
```

退出码 0 = 通过，1 = 有 ERROR。可以直接进 CI。

### ① 的输出长这样

```
· [INFO] title: 已声明中文容量：24 字 / 2 行
! [WARN] subtitle: 只有 maxLength=36（按英文估），中文实际约只能放 22 字；建议补 x-zh
✗ [ERROR] body: 字符串字段没有 maxLength，也没有中文容量声明，中文一定会溢出
· [INFO] summary: 6 个字符串字段，其中 1 个声明了中文容量
✗ [ERROR] summary: 还有 5 个字段未做中文适配
FAIL — 2 error / 1 warn
```

## 规则从哪来

不是拍脑袋，是踩出来的。这些数字来自真实渲染事故：

| 现象 | 根因 | 规则 |
|---|---|---|
| 标题挤成三行 | 英文 maxLength 直接套中文 | 折算系数 0.62 |
| 标点跑到行首 | 按宽度硬折行，没做禁则 | `noLineStart` |
| 末行只剩一个字 | 折行没有孤字回退 | 末行 <4 字就从上行挪字 |
| 字太小看不清 | 用缩字号来"容纳"超长文案 | 容量写死，超了就改写 |
| 字幕压到平台按钮 | 不知道竖屏底部有 24% UI 保留区 | 安全区按 bottomRatio 0.24 |

## 目录

```
motion-zh/
├── scripts/
│   ├── check_zh.py          # 检查器（纯标准库，无依赖）
│   └── rules.json           # 规则表，可改
├── templates/
│   └── finance-cards/       # 示例 .motion 源码（已通过官方 inspect）
└── tools/
    └── render_probe.js      # 抽帧验证脚本
```

## 边界

- 只管**排版与容量**，不管内容好坏。
- 只覆盖中文。英文模板请用官方规则。
- 检查器不渲染，不做像素级测量；真正的"会不会溢出"还要靠 `render_probe.js` 抽帧看一眼。

## 许可

MIT。检查器零依赖，只用 Python 标准库。
