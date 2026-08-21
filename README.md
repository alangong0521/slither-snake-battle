# 贪吃蛇大作战（slither.io 风格安卓贪吃蛇）

单文件 Canvas 2D 游戏内核 + 原生安卓 WebView 壳，支持单人 AI 对战与局域网多人（3+）联机。

## 目录结构

```
snake_apk/
├── app/
│   ├── build.gradle                 # versionCode/versionName/签名配置
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── assets/index.html        # 游戏本体（全部逻辑，零依赖，可离线运行）
│       ├── java/com/kimi/snakegame/MainActivity.java  # WebView壳+LAN TCP桥(多客户端)
│       └── res/                     # 图标
├── snake.keystore                   # 固定签名（覆盖安装的基石，务必保管好）
│                                    #   alias=snake 密码 snake2026/snake2026
│                                    #   cert SHA-256=a70ec2fd…7481b6
├── tests/
│   ├── run_tests.py                 # 发布前测试集（64 项，全绿才能发布）
│   └── lan_sim3_tpl.html            # 三人联机仿真模板
├── docs/
│   ├── TESTSUITE.md                 # Bug 档案（根因/修复/用例对照）+ 测试集说明
│   ├── CHANGELOG.md                 # 版本变更记录
│   └── HANDOFF.md                   # 工程移交说明（架构/约定/坑）
└── build.gradle / settings.gradle / gradle.properties
```

## 构建

需要 JDK17 + Android SDK + Gradle 8.9（AGP 8.6.1，compileSdk 35 / minSdk 24）。

```bash
gradle assembleDebug   # 产物 app/build/outputs/apk/debug/app-debug.apk（固定签名，可覆盖安装）
```

发版 checklist：
1. `python3 tests/run_tests.py` 全部通过
2. `index.html` 的 `VERSION` 与 `app/build.gradle` 的 `versionName` 同步 +0.1，`versionCode` +1
3. APK 命名带版本号：`贪吃蛇大作战_vX.X.apk`
4. `docs/CHANGELOG.md` 追加变更记录

## 测试

见 [docs/TESTSUITE.md](docs/TESTSUITE.md)。核心机制：headless chromium 虚拟时间下完整运行
游戏与三人联机仿真，逐项断言 [TEST]/[SIM] 日志。
