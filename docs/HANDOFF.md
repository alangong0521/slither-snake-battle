# 贪吃蛇大作战 — 工程移交说明（HANDOFF）

> 本文档面向接手开发的 AI / 开发者。读完本文即可理解全部架构、构建方法、测试方法和既有约定。
> 当前版本：**v2.2（versionCode 13，versionName '2.2'）**，日期：2026-08。

---

## 1. 项目概述

一款仿「贪吃蛇大作战 / slither.io」的休闲竞技游戏，形态为 **Android APK**：

- 玩家蛇在圆形竞技场中吃光点长大，撞到其他蛇身体即阵亡，可围杀对手吃残骸
- 9 条 AI 蛇（含开局 2 条巨蛇），实时排行榜
- 长度 1000 解锁金色光环，长度 2000 进化彩虹神蛇
- 自定义名字 + 8 色皮肤，历史最高分 TOP 10 本地持久化
- WebAudio 实时合成的背景音乐 + 音效（零音频文件）
- **局域网双人联机对战**（无服务器，一台设备做主机 TCP 直连）
- 全设备视野统一（900×500 世界区域 + 遮幅），保证联机公平

**技术形态**：原生 Android 壳（单个 `MainActivity` + WebView + JavaScriptInterface 桥），游戏 100% 逻辑在**单个 HTML 文件** `app/src/main/assets/index.html` 里（原生 JS + Canvas，无任何外部依赖、无网络请求、完全离线可玩）。

## 2. 文件结构

```
snake_game_handoff/
├── HANDOFF.md                  ← 本文档
├── CHANGELOG.md                ← 全部版本修改记录
├── 贪吃蛇大作战_v2.0.apk        ← 当前构建产物（debug 签名）
└── snake_apk/                  ← Android 工程（Gradle）
    ├── settings.gradle         ← 仓库含阿里云/腾讯镜像（国内构建快）
    ├── build.gradle            ← AGP 8.6.1
    ├── gradle.properties
    └── app/
        ├── build.gradle        ← applicationId com.kimi.snakegame, minSdk 24, targetSdk 34, compileSdk 35
        └── src/main/
            ├── AndroidManifest.xml   ← 含 INTERNET/WIFI 权限（联机用）
            ├── assets/index.html     ← ★ 游戏本体（所有改动都在这里）
            ├── java/com/kimi/snakegame/MainActivity.java  ← WebView 壳 + LAN TCP 桥 + exitApp
            └── res/                  ← 各密度图标 + 自适应图标（PIL 绘制）
```

**开发原则（重要）**：改游戏 = 改 `index.html`；只有涉及原生能力（网络、退出、震动等）才动 `MainActivity.java`。

## 3. 核心架构（index.html）

单文件 IIFE，主要模块自上而下：

| 模块 | 关键点 |
|---|---|
| 常量 | `WORLD_R=2300`（圆形世界）、`FOOD_N=170`（环境食物数）、`AI_N=9`、`SP=5`（身体节点间距px）、`VIEW_W=900 VIEW_H=500`（锁定视野） |
| 蛇数据结构 | `pts`（身体节点数组，头为 [0]）、`trail`（蛇头历史轨迹）、`score`（分数/长度）、`vlen`（浮点可视长度）、`angle/tAngle`、`boost`、`grace`（出生无敌帧）、`aggro`（AI 攻击性 0.2~0.6） |
| 移动 `moveSnake` | 速度 `sp=(3.0/zoomOf)*(1+(1-zoomOf)*0.4)`，加速 ×1.8 且每帧燃烧 0.10 长度并掉食物；**轨迹跟随**：每帧 `trail.unshift(蛇头)`，按弧长把节点精确铺在轨迹上；`vlen` 以 +0.35/-0.6 每帧速率追踪 score → **尾巴平滑生长/回缩**（根治了闪烁和跳跃，不要改回整数取整！）；边界 = 贴边滑行（去掉速度径向分量），永不死亡 |
| 相机 `render` | `sc=min(W/VIEW_W, H/VIEW_H)`，`zoom=sc*zoomOf(player)`，`ctx.clip` 到居中矩形 —— **任何设备看到的世界区域完全一致**（公平性核心，勿动）；超出的屏幕区域为深色遮幅 + 细线框 |
| AI `aiThink` | 每 8 帧思考：收集附近蛇体采样点为威胁 → 9 个候选方向打分（目标对齐 +40、保持方向 +30、掉头 -250、威胁 -(距离差×4)）；大蛇靠近会逃跑（并加速）、小蛇靠近按 aggro 概率预判拦截、寻食半径 900 |
| 碰撞 `collisions` | ①**蛇头对撞**：头距 < (r1+r2)×0.6 → 分数大 1.15× 者胜，否则同归于尽；②头 vs 其他蛇身体（头部 8 节点豁免），宽相用"头距 > 身长"快速剔除，采样步长自适应；出生无敌帧双方豁免 |
| 小地图 `drawMap` | 左下圆形雷达（`#map` canvas，每 10 tick 重绘）：世界环 + 全部存活蛇位置点（颜色=蛇色），自己大点+白圈+「我」字、联机对方彩色环（快照 `h` 位标记人类）、AI 小点 |
| 道具系统 | `powers` 数组 + `PWT=[mag,shd,zm,x5,mush]`：磁铁(600帧吸豆)/护盾(480帧免死)/放大镜(600帧视野×0.8 zoom)/×5豆(480帧)/蘑菇(+500)；效果字段 `magT/shdT/zmT/x5T/fzT` 存到期 tick；击杀充能 `skillN`≤3 → `activateSkill` 狂暴 480 帧（加速免费+磁铁+提速 1.25×）；`killChain` 8 秒内连杀 +50×连击；死亡清空全部效果；AI 会寻道具、遇敌放技能 |
| 配色系统 | `COLFAMS` 8 色系 × 3 色阶 = 24 色（`PCOLORS` 为扁平池）；选色 UI = `#famRow` 色系 + `#colorRow` 色阶；AI 用 `aiColorFree()` 避开人类与 AI 已占色（开局/hello/重生校验 `fixColorConflicts`） |
| 成长 | 每颗豆 `score += f.v`（**必须 ≥1**，曾因 0.9 取整导致"吃豆不长"）；死亡尸体每 3 节点掉 val=2 食物 |
| 渲染 | 蛇身 = 单条 path stroke（不是逐点圆，这是性能关键）；≥1000 金环（3 层脉动环 + 8 光点）、≥2000 分段 hsl 彩虹身 + 变色环 |
| 音频 | WebAudio 合成：BGM = C-G-Am-F 8 小节循环（lookahead 调度器），音效 = 吃豆（连击升调）/击杀/阵亡/开局/加速；`localStorage snake_audio` 记开关 |
| 存储 | `snake_hs` = TOP10 历史榜（阵亡时写入）；`snake_audio` = 音频开关 |
| 联机 `LAN` | 见第 4 节 |
| 循环 | rAF 主驱动（15ms 帧限）+ 看门狗（rAF 停 300ms 自动切 setTimeout）；`__FORCE_FB__` 可强制定时器驱动（测试用） |

### 输入

- 方向盘（左下，Pointer Events + setPointerCapture）、加速按钮（右下，`boostIds` 集合记录按住的手指，**每帧重算** `player.boost`——这是修"加速状态粘住"的关键机制，勿改回 sticky 标志）
- 鼠标：移动转向、按住左键加速；键盘：空格暂停、左右方向键微调
- `visibilitychange` 自动暂停

## 4. 局域网联机（LAN）

**模型：主机权威（host-authoritative），2 人，TCP 直连，端口 7799。**

- **Java 侧**（`MainActivity.Bridge`）：`lanHost(port)` 起 ServerSocket 并回传本机 IP；`lanJoin(ip,port)` 连接；`lanSend(s)` 投递到**单写线程 + LinkedBlockingQueue(256)**（队列满丢最旧保最新——勿改回每条消息 new Thread，那是联机卡顿的根因）；收到行文本回调 `window.__lanOnMsg(json)`；状态回调 `window.__lanStatus(s)`（`listening ip=x / connected / closed / error x`）；`exitApp()` 关闭应用
- **JS 侧**：`LAN.mode` 0 单机 / 1 主机 / 2 客户端
- **消息协议**（JSON 行）：
  - C→H：`{t:'hello',n,c}` 入场（名字颜色）、`{t:'in',a,b}` 输入（20Hz，角度+加速）、`{t:'rv'}` 请求复活、`{t:'sk'}` 释放技能
  - H→C：`{t:'you',i}` 分配蛇索引、`{t:'start'}` 开局、`{t:'snap',...}` 快照（10Hz）
- **快照**（7.5Hz）：每条蛇 `{i,n,c,s,k,a,g,h(是否人类),e(效果六格+技能层数),p(扁平整数坐标)}`，坐标采样步长按长度自适应（≤160 点/蛇，强制含尾点）+ 客户端玩家 1600px 内食物（≤100 个）+ `pw` 道具列表；客户端输入上报 20Hz
- **客户端**：非本机蛇按 0.3 系数向快照指数平滑；本机蛇本地预测（moveSnake）+ 蛇头 0.12 软校正；分数/存活以主机为准；阵亡→`showDeath`→`{t:'rv'}` 复活；主机开局后加入方看到「加入战斗」确认按钮才入场
- **已知限制**：仅 2 人；无插值缓冲（LAN 低延迟下够用）；主机退出即散场；跨网段不可达（需同 Wi-Fi）

## 5. 测试基础设施（重要约定）

**每次改动必须先在仿真环境验证通过再发布**（用户硬性要求）。无头 Chromium + 虚拟时间驱动：

```bash
# 注入自动驾驶后运行 60 秒虚拟时间，导出 DOM 读 #testlog
sed 's|<body>|<body><script>window.__AUTOPILOT__=true;</script>|' \
  snake_apk/app/src/main/assets/index.html > /tmp/t.html
chromium --headless=new --disable-gpu --no-sandbox --window-size=1180,800 \
  --virtual-time-budget=60000 --dump-dom file:///tmp/t.html 2>/dev/null | grep -o '\[TEST\][^<]*'
```

**内置测试钩子**（游戏代码自带，生产无副作用）：

| 钩子 | 作用 |
|---|---|
| `__AUTOPILOT__` | 自动开局、AI 代打玩家、每秒输出 `[TEST]` 状态、含边界滑行/方向盘/阵亡复活/巨蛇成长断言日志 |
| `__EATTEST__` | 吃豆专项：单豆必 +1、连续 6 豆、加速防粘断言 |
| `__AURATEST__` | 强制 score=1100/2100，验证金环/彩虹渲染无报错 |
| `__LANTEST__` | 联机日志（快照 sent/recv、sync、hostScore 对账） |
| `__FORCE_FB__` | 强制 setTimeout 循环（虚拟时间下 rAF 不驱动时用） |

**联机仿真**：单个父页面嵌两个 `lan_game_fb.html` iframe，`postMessage` 中转模拟 TCP，父页面自动点创建/加入/确认，校验两端 `snakes` 数量与 `myScore==hostScore`（详见 CHANGELOG v1.7/v1.9 验证记录；注意父页面读日志要轻量，只取末尾几行，否则虚拟时间下父页面会卡死造成"客户端冻结"假象）。

**相机一致性断言**：`[TEST] viewWH=901x501` 在任意窗口尺寸下必须一致。

## 6. 构建 APK

环境：JDK 17 + Android SDK（platforms;android-35 + build-tools;34.0.0）+ Gradle 8.9。国内镜像下载快：

```bash
# SDK 组件（腾讯镜像，直接解压即安装）
curl -O https://mirrors.cloud.tencent.com/AndroidSDK/platform-35_r02.zip      # → platforms/android-35
curl -O https://mirrors.cloud.tencent.com/AndroidSDK/build-tools_r34-linux.zip # → build-tools/34.0.0（目录原名 android-14 需改名）
curl -O https://mirrors.cloud.tencent.com/gradle/gradle-8.9-bin.zip
# licenses/android-sdk-license 写入三个接受哈希（见既有脚本）
cd snake_apk && echo 'sdk.dir=/path/to/android-sdk' > local.properties
ANDROID_HOME=/path/to/android-sdk /path/to/gradle-8.9/bin/gradle assembleDebug
# 产物：app/build/outputs/apk/debug/app-debug.apk
```

**签名（v2.2 起已解决）**：工程内置固定证书 `snake_apk/snake.keystore`（alias `snake`，store/key 密码均为 `snake2026`，有效期 30 年），`app/build.gradle` 的 signingConfigs 对 debug/release 都启用它。**务必保管好这个 keystore 文件**——只要它在，任何环境构建出的 APK 签名一致，用户可直接覆盖安装；丢失则用户又需卸载重装。证书 SHA-256：`a70ec2fd:c7a1416b:bb9e8fee:45f6b826:b7e4617e:74e06bd9:542ddade:867481b6`。

## 7. 版本历史

见 `CHANGELOG.md`（v1.0 → v2.0 全部修改记录，含每个 bug 的根因）。

## 8. 既有约定与注意事项

1. **尾巴生长机制勿回退**：`vlen` 浮点追踪 + 弧长布点是修了两轮（闪烁、跳跃）才稳定的方案
2. **加速状态勿用 sticky 标志**：必须每帧从 `boostIds` 重算
3. **相机锁区勿动**：`VIEW_W/VIEW_H + clip` 是联机公平性核心
4. **吃豆必须 ≥1 分**（取整 bug 教训）
5. 性能三原则：蛇身单 path、碰撞宽相剔除、视野裁剪（clip + 距离剔除）
6. 用户设备：荣耀 X10 Pro 平板（智能分辨率）+ 真我 GT7 Pro（2376×1080）——改 UI 后需在 ~864×393 小横屏验证
7. 发布流程：仿真验证 → versionCode+1 / versionName 升级 → 构建 → apksigner verify → 提醒用户先卸载旧版

## 9. 建议的后续方向

- 固定签名 keystore（见第 6 节）
- 联机：>2 人（主机广播多个客户端）、断线重连、观战
- 客户端插值缓冲（snapshot A/B lerp）替代指数平滑，弱网更稳
- 皮肤/地图主题、更多 AI 难度档位
- iOS 不支持 APK；iPad 可尝试 Safari「添加到主屏幕」直接玩 index.html
