# 性格分析 · 落地页（xingge-web）

微信小程序「性格分析 / MBTI 十六型人格测试」的 Web 落地页。纯静态，无构建、无运行时依赖。

- **线上用途**：让第一次来的人 30 秒内明白产品是什么、凭什么信、下一步点哪里，最终引流到小程序码。
- **打开方式**：双击 `index.html` 即可（`file://` 直接可看），或丢到任意静态托管。

## 结构

```
index.html                 页面（图鉴 / 报告两个区块由脚本生成后回填）
docs/spec.md               规格（先于代码，行为以它为准）
assets/css/style.css       样式（浅色 / 深色跟随系统）
assets/js/main.js          交互增强（筛选、切换、动效；无 JS 仍可读）
assets/data/personalities.js  由工具生成的 16 型数据
assets/img/poster-qr.png   小程序码
tools/build_data.py        从 xingge-app-kuikly 生成数据 + 回填页面
tools/verify.py            自动验证（112 项）
```

## 数据从哪来（单一真源）

16 型文案、配色、六维分数、题库统计**不在本仓库二次抄写**，
全部由 `tools/build_data.py` 从相邻的 `xingge-app-kuikly` 读取：

| 数据 | 源文件 |
| --- | --- |
| 16 型基础 + 文案 | `xingge-app-kuikly/shared/src/commonMain/assets/common/result.json` |
| 六维工作画像 | `xingge-app-kuikly/shared/.../data/json/ProfileData.kt` |
| 题库统计 | `xingge-app-kuikly/shared/src/commonMain/assets/common/tiku.json` |
| 小程序码 | `xingge-app-kuikly/shared/.../mbti/poster-qr.png` |

源结构变了、或者源文件缺失，脚本会**报错退出**，不会静默生成空页面。

## 使用

```bash
# 生成 / 更新页面与数据（改完源仓库后重跑）
python3 tools/build_data.py

# 校验（数据完整性 + 一致性 + HTML 结构 + 资源 + 文案红线 + 无障碍）
python3 tools/verify.py

# 本地预览
python3 -m http.server 8000        # 然后打开 http://localhost:8000
# 或直接双击 index.html
```

依赖：仅 Python 3 标准库。

## 品牌名

当前站点名用仓库 README 的称呼「性格分析」。小程序正式名尚未定
（源仓库 `docs/ops/miniapp/info.md` 提议「知己赋」，`review-notes.md` 明确说账号名未最终确认）。
改名只需改 `tools/build_data.py` 里的 `BRAND` 常量，重跑一次即可。

## 设计要点

- 视觉参考 Apple Design Guide：大留白、层级靠字号字重、色彩克制、动效只做入场淡入。
- 颜色：以 16 型主色为点缀，深色型色（如 `#22223B`）会换算成白底 ≥4.5:1 的 `text` 色和浅底 `tint` 色，避免对比度不足。
- 深色模式跟随系统；`prefers-reduced-motion` 下关闭动效。
- 文案红线：不出现「诊断」「治疗」等医疗词（`verify.py` 会检查）。
