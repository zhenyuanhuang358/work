# Screenshot Background Assets

此目录存放 PPT Skill 截图美化功能所需的预生成背景图。

## 目录结构

```
screenshot-backgrounds/
├── style-a/          # 电子杂志×电子墨水风格（5套）
└── style-b/          # 瑞士国际主义风格（4套）
```

## 所需资产清单

### Style A — 电子杂志风 (`style-a/`)

| 文件名 | 主题 | 视觉说明 |
|--------|------|---------|
| `monocle-classic.webp` | 墨水经典 | 黑白灰纸张纹理、柔和阴影、细颗粒 |
| `indigo-porcelain.webp` | 靛蓝瓷 | 靛蓝低饱和墨色、纸感渐变、轻微噪点 |
| `forest-ink.webp` | 森林墨 | 模糊植物阴影、低饱和绿色、纸张颗粒 |
| `kraft-paper.webp` | 牛皮纸 | 暖纸色、淡墨阴影、复古印刷颗粒 |
| `dune.webp` | 沙丘 | 沙色/灰调柔和渐变、低对比、留白安静 |

### Style B — 瑞士国际主义风 (`style-b/`)

| 文件名 | 主题色 | 视觉说明 |
|--------|--------|---------|
| `ikb-dot-gradient.webp` | IKB 蓝 | 点阵 + 低对比蓝色渐变，避免亮蓝大色块 |
| `lemon-grid.webp` | 柠檬黄 | 纯网格 + 稀疏点阵，黄色只做低透明细线/点 |
| `lemon-green-dot-shadow.webp` | 柠檬绿 | 点阵 + 阴影场，绿色只做轻微光感 |
| `safety-orange-halftone.webp` | 安全橙 | 模块化半调点阵 + 暗部阴影，橙色低占比 |

## 生成规范

所有背景图均为 1920×1080 (16:9) WebP，必须满足：
- crop-safe：裁成 21:9 / 16:10 / 4:3 / 1:1 都不能暴露"被裁掉"的痕迹
- 四角安静（截图可能居中、左上、右下或被裁成不同尺寸）
- 无文字、logo、图标、人物、设备、边框、明显主体或方向性构图

### Style A 生成提示词

```
16:9 crop-safe screenshot background for an editorial magazine / e-ink PPT system. Warm off-white paper texture, subtle ink wash, fine film grain, low contrast, quiet center and quiet corners, no text, no logo, no objects, no border, no focal subject. Suitable for cropping to 21:9, 16:10, 4:3, or 1:1.
```

根据主题调整描述（如 forest-ink 加入"blurred plant shadows, desaturated green"）。

### Style B 生成提示词

```
16:9 crop-safe screenshot background for a Swiss International Style PPT system. Pure off-white base, ultra-subtle 16-column grid and sparse dot matrix, one accent color only: [theme color], used at very low opacity as thin lines or tiny dots, no large bright color blocks. Quiet center and quiet corners, no text, no logo, no objects, no border, no focal subject. Suitable for cropping to 21:9, 16:10, 4:3, or 1:1.
```

将 `[theme color]` 替换为对应主题色（IKB Blue / Lemon Yellow / Lemon Green / Safety Orange）。

## 使用规则

- 截图美化时**优先使用此处资产**，不要实时生成背景
- 只有用户要求新风格或现有主题缺失时，才用上方提示词通过 GPT-M 2.0 生成新资产
- 详细使用规则见 `references/screenshot-framing.md`
