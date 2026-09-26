# 一条卖方仓位的一周（GM 79P，2026-09-18 → 09-25）

45 秒竖屏短片，路径＝awesome-opus-5-5-videos playbook 第 1 套「零外部视觉素材的代码动画」。

| 文件 | 作用 |
|---|---|
| `storyboard.md` | 7 镜分镜（时间/画面/动作/字幕/转场）与数据来源 |
| `film.html` | 全部画面：`render(t)` 只由时间 t 决定，无随机数、无外部图片/视频/字体 |
| `render.py` | 逐帧取 canvas → ffmpeg(libx264) 编码；`--sheet` 出九帧缩略图 |
| `out/gm_week_45s.mp4` | 成片 1080×1920 · 30fps · 无音轨 |
| `out/contact_sheet.png` / `out/transitions.png` | 审片用：九帧取样 / 转场帧 |

## 重新渲染
```
python3 -m pip install --break-system-packages playwright==1.56.0 imageio-ffmpeg   # 1.56 对应预装 Chromium 1194（profile 1.2h）
python3 render.py 0 45 out/gm_week_45s.mp4      # 约 50 秒
python3 render.py 0 5 out/sample.mp4            # 只出前 5 秒样片
python3 render.py --sheet out/contact_sheet.png
```
中文字体用系统自带文泉驿正黑（无粗体字重，粗体靠描边模拟）；数字用 Liberation Serif。

## 已踩过的坑
- **绘图辅助函数的透明度必须「相乘」不能「赋值」**（`globalAlpha *= a`）。赋值会让外层镜头的淡入淡出对内部文字失效，
  转场时两个镜头的文字全不透明地叠在一起。文字溢出检测抓不到这类问题——**转场帧必须单独抽查**。
- 镜头之间「先淡出到纸色、再淡入」，不做交叉叠化：两套文字半透明叠在一起比硬切更难看。
