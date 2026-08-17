#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
贪吃蛇大作战 — 发布前完备性测试集
用法: python3 tests/run_tests.py
依赖: chromium (headless), python3
原理: 从当前 app/src/main/assets/index.html 动态生成测试页, 用 headless chromium
      在虚拟时间下完整运行游戏, 抓取 [TEST]/[SIM] 日志逐项断言。
任何一项 FAIL 都会以非零码退出 — 未全部通过不得发布。
"""
import os, re, subprocess, sys, shutil, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'app/src/main/assets/index.html')
WORK = os.path.join(ROOT, 'tests/.work')

CHROMIUM = None
for c in ['chromium', 'chromium-browser', 'google-chrome', 'chrome']:
    if shutil.which(c):
        CHROMIUM = shutil.which(c)
        break
if not CHROMIUM:
    print('FATAL: 未找到 chromium'); sys.exit(2)

def run_chromium(url, budget, extra=None, window='1254,752', dom=False):
    args = [CHROMIUM, '--headless=new', '--disable-gpu', '--no-sandbox',
            '--allow-file-access-from-files', '--window-size=' + window,
            '--virtual-time-budget=' + str(budget), '--enable-logging=stderr']
    if dom:
        args.append('--dump-dom')
    if extra:
        args += extra
    args.append(url)
    p = subprocess.run(args, capture_output=True, text=True, timeout=300)
    out = p.stderr + '\n' + p.stdout
    logs = []
    for m in re.finditer(r'CONSOLE[^"]*"((?:[^"\\]|\\.)*)"', out):
        logs.append(m.group(1).replace('\\"', '"').replace('\\n', '\n'))
    return logs, (p.stdout if dom else '')

results = []
def check(tid, name, cond, detail=''):
    results.append((tid, name, bool(cond), detail))
    print(('PASS' if cond else 'FAIL') + '  ' + tid + '  ' + name + ('  | ' + str(detail) if detail else ''))

def gen_files():
    if os.path.exists(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK)
    src = open(INDEX, encoding='utf-8').read()
    # ---- 单人测试页: 吃豆/对冲/道具/技能/光环/间距/撞体/多点触控/技能视野 ----
    probes = r"""
if(window.__BODYTEST__&&tickN===700){
var big=snakes[1],sm=snakes[2];
big.alive=true;big.grace=0;big.score=1000;big.vlen=1000;big.pts=[];for(var bi=0;bi<1000;bi++)big.pts.push({x:-600+bi*1.2,y:1200});big.trail=big.pts.map(function(q){return{x:q.x,y:q.y};});big.angle=0;big.tAngle=0;big.aiA=0;big.aiT=99999;
sm.alive=true;sm.grace=0;sm.score=30;sm.vlen=30;sm.pts=[];for(var si=0;si<30;si++)sm.pts.push({x:0,y:1100-si*5});sm.trail=sm.pts.map(function(q){return{x:q.x,y:q.y};});sm.angle=Math.PI/2;sm.tAngle=Math.PI/2;sm.aiA=Math.PI/2;sm.aiT=99999;
slog('[TEST] bodycross setup');
}
if(window.__BODYTEST__&&tickN===950)slog('[TEST] bodycross smallAlive='+(snakes[2].alive?1:0));
if(tickN===400&&window.__SKZOOM__){player.skillN=2;player.fzT=0;player.zmT=0;window.__vz0=zoomOf(player);activateSkill(player);window.__vz1=zoomOf(player);slog('[TEST] skillzoom viewGrow='+(__vz0/__vz1).toFixed(3)+' zmTicks='+(player.zmT-tickN));}
if(tickN===1000&&window.__SKZOOM__)slog('[TEST] skillzoom expired='+((player.zmT-tickN)<=0?1:0));
if(tickN===1100&&window.__MTTEST__){try{
var joy=$('joy');var jr=joy.getBoundingClientRect();
joy.dispatchEvent(new PointerEvent('pointerdown',{pointerId:11,clientX:jr.left+60,clientY:jr.top+60,bubbles:true}));
var sb=$('skillBtn');sb.style.display='block';player.skillN=1;player.fzT=0;player.zmT=0;
var sr=sb.getBoundingClientRect();
sb.dispatchEvent(new PointerEvent('pointerdown',{pointerId:22,clientX:sr.left+20,clientY:sr.top+20,bubbles:true}));
slog('[TEST] multitouch skill fz='+((player.fzT||0)>tickN?1:0));
joy.dispatchEvent(new PointerEvent('pointerup',{pointerId:11,bubbles:true}));
}catch(e){slog('[TEST] mt err '+e.message);}}
if(tickN===59){player.score=26;} // 视野测量前固定分数, 保证不同设备 z0 一致
if(tickN===700&&window.__SPAWNTEST__){var ts3=snakes[3];ts3.alive=false;ts3.respawn=2;window.__spawnCk=ts3;}
if(tickN>704&&window.__SPAWNTEST__&&window.__spawnCk&&window.__spawnCk.alive){var sd=dist(window.__spawnCk.pts[0].x,window.__spawnCk.pts[0].y,player.pts[0].x,player.pts[0].y);slog('[TEST] spawnDist='+Math.round(sd));window.__spawnCk=null;}
if(tickN===800&&window.__CHAINTEST__){var kl=snakes[4];kl.alive=true;kl.killChain=0;kl.lastKillT=-9999;for(var ci=5;ci<11&&ci<snakes.length;ci++){var vt=snakes[ci];vt.alive=true;vt.grace=0;vt.pts=[];for(var vi=0;vi<10;vi++)vt.pts.push({x:1500+vi*5,y:1500});vt.trail=vt.pts.map(function(q){return{x:q.x,y:q.y};});die(vt,kl);}slog('[TEST] chainCap chain='+kl.killChain);}
if(tickN===300&&window.__MUSHTEST__){window.__mushBase=player.score;player.grace=999999;powers.length=0;player.mushs=[];player.mushDrain=0;applyPower(player,'mush');slog('[TEST] mush plus='+Math.round(player.score-window.__mushBase));}
if(tickN===1250&&window.__MUSHTEST__){slog('[TEST] mush mid drain='+(player.mushDrain||0));}
if(tickN===1500&&window.__MUSHTEST__){slog('[TEST] mush end drain='+(player.mushDrain||0));}
"""
    g = src.replace('<body>', '<body><script>window.__AUTOPILOT__=true;window.__FORCE_FB__=true;'
        'window.__EATTEST__=true;window.__AURATEST__=true;window.__HEADTEST__=true;'
        'window.__POWTEST__=true;window.__BODYTEST__=true;window.__SKZOOM__=true;window.__MTTEST__=true;'
        'window.__SPAWNTEST__=true;window.__CHAINTEST__=true;window.__MUSHTEST__=true;</script>', 1)
    g = g.replace('if(window.__EATTEST__){', probes + '\nif(window.__EATTEST__){', 1)
    open(os.path.join(WORK, 'g.html'), 'w', encoding='utf-8').write(g)
    # ---- 联机节点页 ----
    fb = src.replace('<body>', '<body><script>window.__FORCE_FB__=true;window.__LANTEST__=true;window.__AUTOPILOT__=true;</script>', 1)
    fb = fb.replace("init();\n})();",
        "init();\nwindow.__G={get LAN(){return LAN},get player(){return player},get snakes(){return snakes},"
        "get foods(){return foods},get cv(){return cv},get remotes(){return remotes},get tickN(){return tickN},"
        "get paused(){return paused},get DBG(){return DBG},die:function(s,k){die(s,k);},mkSnake:mkSnake,"
        "lanSend:function(o){lanSend(o);}};\n})();")
    open(os.path.join(WORK, 'lan_fb.html'), 'w', encoding='utf-8').write(fb)
    # ---- 三人联机仿真 ----
    sim = open(os.path.join(ROOT, 'tests/lan_sim3_tpl.html'), encoding='utf-8').read()
    sim = sim.replace('__FB_PATH__', os.path.join(WORK, 'lan_fb.html'))
    open(os.path.join(WORK, 'lan_sim3.html'), 'w', encoding='utf-8').write(sim)

def solo_tests():
    logs, _ = run_chromium('file://' + os.path.join(WORK, 'g.html'), 26000)
    joined = '\n'.join(logs)
    errs = [l for l in logs if l.startswith('[ERR]')]
    check('T01', '游戏启动/10蛇170豆', '[TEST] boot ok' in joined)
    check('T02', 'localStorage可用', '[TEST] ls=ok' in joined)
    m = re.search(r'\[EAT\] final score=([\d.]+) pts=(\d+)', joined)
    check('T03', '吃豆成长(分数/长度同步)', m and float(m.group(1)) > 100 and int(m.group(2)) > 100,
          m.group(0) if m else '无日志')
    check('T04', '对冲击杀判定(同体型同归于尽)', 'head-on kill tick=' in joined and 'A=0 B=0' in joined)
    check('T05', '道具三效果生效(磁/镜/×2)', 'pow effs(m/z/x5)=111' in joined)
    check('T06', '击杀技能充能+狂化', 'skill fz=1' in joined)
    m = re.search(r'skillzoom viewGrow=([\d.]+) zmTicks=(\d+)', joined)
    check('T07', '技能视野扩大25%持续10秒', m and abs(float(m.group(1)) - 1.25) < 0.01 and int(m.group(2)) == 600,
          m.group(0) if m else '无日志')
    check('T08', '技能视野到时自动消失', 'skillzoom expired=1' in joined)
    check('T09', '左手按住方向盘右手放技能(多点触控)', 'multitouch skill fz=1' in joined)
    check('T10', '金色光环1000分解锁', 'aura gold on' in joined)
    check('T11', '彩虹蛇非第一名被阻止', 'rainbow blocked' in joined)
    check('T12', '彩虹蛇第一名唯一进化', 'rainbow on' in joined)
    m = re.search(r'spacing maxErr=([\d.]+)', joined)
    check('T13', '蛇身间距恒定(尾巴不跳跃)', m and float(m.group(1)) <= 5.01, m.group(0) if m else '无日志')
    check('T14', '小蛇穿千分大蛇身体必死', 'bodycross smallAlive=0' in joined)
    check('T15', '历史最高分保存', 'hs count=1' in joined)
    check('T16', '运行无JS异常', len(errs) == 0, ';'.join(errs[:3]))
    m = re.search(r'spawnDist=(\d+)', joined)
    check('T30', '重生点远离玩家(≥950px)', m and int(m.group(1)) >= 950, m.group(0) if m else '无日志')
    m = re.search(r'chainCap chain=(\d+)', joined)
    check('T31', '连杀奖励封顶(≤5级)', m and int(m.group(1)) <= 5, m.group(0) if m else '无日志')
    m1 = re.search(r'mush plus=(\d+)', joined);mm = re.search(r'mush mid drain=(\d+)', joined);m2 = re.search(r'mush end drain=(\d+)', joined)
    check('T35', '蘑菇+500限时15秒后渐进恢复', m1 and int(m1.group(1)) == 500 and mm and 100 < int(mm.group(1)) < 500 and m2 and int(m2.group(1)) == 0,
          ' / '.join(x.group(0) if x else '无日志' for x in [m1, mm, m2]))

def view_tests():
    vals = []
    for w in ['1254,752', '1188,540']:
        logs, _ = run_chromium('file://' + os.path.join(WORK, 'g.html'), 4000, window=w)
        m = None
        for l in logs:
            mm = re.search(r'viewWH=(\d+)x(\d+)', l)
            if mm:
                m = mm
                break
        vals.append((int(m.group(1)), int(m.group(2))) if m else None)
    ok = all(vals) and abs(vals[0][0] - vals[1][0]) <= 8
    check('T17', '手机/Pad宽度视野一致', ok, str(vals))
    ok2 = all(vals) and vals[0][1] > vals[1][1]
    check('T18', 'Pad高度视野多于手机', ok2, str(vals))

def version_test():
    _, dom = run_chromium('file://' + os.path.join(WORK, 'g.html'), 2500, dom=True)
    m = re.search(r'id="verTag"[^>]*>([^<]+)<', dom)
    ver_src = re.search(r"var VERSION='([^']+)'", open(INDEX, encoding='utf-8').read())
    gradle = open(os.path.join(ROOT, 'app/build.gradle'), encoding='utf-8').read()
    ver_gradle = re.search(r"versionName '([^']+)'", gradle)
    check('T19', '主页显示版本号', m and m.group(1).startswith('版本 v'), m.group(1) if m else '未找到')
    check('T20', '版本号与build.gradle一致',
          m and ver_src and ver_gradle and m.group(1) == '版本 v' + ver_src.group(1) == '版本 v' + ver_gradle.group(1),
          '页面=%s js=%s gradle=%s' % (m.group(1) if m else '?', ver_src.group(1) if ver_src else '?', ver_gradle.group(1) if ver_gradle else '?'))

def lan_tests():
    logs, _ = run_chromium('file://' + os.path.join(WORK, 'lan_sim3.html'), 37000, window='1300,700')
    joined = '\n'.join(logs)
    check('T21', '主机建房+两客机加入(remotes=2)', 'remotes=2' in joined)
    check('T22', '第三玩家真正入局(ownIdx=11)', 'C ownIdx=11' in joined)
    check('T23', '从机免确认自动进入', joined.count('autoEntered=true') >= 2)
    check('T24', '快照60Hz持续下发', bool(re.search(r'B snaps=([4-9]\d|\d{3,})', joined)))
    for f in ['A', 'B', 'C']:
        m = re.search(f + r' humans:(.*)', joined)
        ok = m and all((n + ':') in m.group(1) for n in ['主机', '客机B', '客机C']) and 'pt@-999' not in m.group(1)
        check('T25' + f, f + '端可见全部玩家蛇身', bool(ok), m.group(1).strip() if m else '无日志')
    m = re.search(r'C foods=(\d+) nearC=(\d+)', joined)
    check('T26', '击杀后尸体豆同步可见', m and int(m.group(1)) >= 100 and int(m.group(2)) > 10,
          m.group(0) if m else '无日志')
    check('T27', '全场暂停同步(tick冻结)', 'pauseSync paused A/B/C=true/true/true tickAfrozen=true' in joined)
    check('T28', '任意玩家恢复全场继续', 'resumeSync paused A/B/C=false/false/false tickCresumed=true' in joined)
    errs = [l for l in logs if l.startswith('[ERR]')]
    check('T29', '联机运行无JS异常', len(errs) == 0, ';'.join(errs[:3]))
    m = re.search(r'C ftween=(\d+)', joined)
    check('T32', '客机豆子平滑补间(带目标点)', m and int(m.group(1)) > 0, m.group(0) if m else '无日志')
    m = re.search(r'B remoteSpacing maxErr=([\d.]+) bad=(\d+) pts=(\d+)', joined)
    check('T33', '客机远端蛇身间距恒定(轨迹重建)', m and int(m.group(2)) <= 2 and float(m.group(1)) <= 5.0 and int(m.group(3)) > 3,
          m.group(0) if m else '无日志')
    m = re.search(r'respawnReset BcPts=(\d+) CcPts=(\d+)', joined)
    check('T34', '重生后蛇身重置为初始长度(跨局不残留)',
          m and 5 < int(m.group(1)) < 80 and 5 < int(m.group(2)) < 80, m.group(0) if m else '无日志')
    m = re.search(r'B noFReset=(\d+) corrN=(\d+)', joined)
    check('T36', '客机无非法整条重建(蛇身不消失)', m and int(m.group(1)) == 0, m.group(0) if m else '无日志')
    check('T37', '自身蛇无持续拖拽校正(死区生效)', m and int(m.group(2)) <= 60, m.group(0) if m else '无日志')
    m = re.search(r'B gaps=(\d+) rebases=(\d+)', joined)
    check('T38', '快照断档自动请求全量重同步', m and int(m.group(1)) >= 1 and int(m.group(2)) >= 1, m.group(0) if m else '无日志')
    m = re.search(r'B watchdog=(\d+) dead=(\d)', joined)
    check('T39', '断线看门狗弹窗(无僵尸局)', m and m.group(1) == '1' and m.group(2) == '1', m.group(0) if m else '无日志')
    # ---- v3.5 回归 ----
    mb = re.search(r'B pause2OK snapLive=(\d) paused=(\d)', joined)
    mc = re.search(r'C pause2OK snapLive=(\d) paused=(\d)', joined)
    mh = re.search(r'host remoteN=(\d+)', joined)
    check('T40', '5秒长暂停后恢复: 从机不掉线不卡死(心跳+pz自愈)',
          mb and mb.group(1) == '1' and mb.group(2) == '0' and mc and mc.group(1) == '1'
          and mc.group(2) == '0' and mh and mh.group(1) == '2',
          '; '.join(x.group(0) for x in [mb, mc, mh] if x) or '无日志')
    m = re.search(r'B deadFrozen alive=(\d) frozen=(\d) ovl=(\d)', joined)
    check('T41', '从机被杀后本地蛇定格(不再可操控移动)', m and m.group(1) == '0' and m.group(2) == '1',
          m.group(0) if m else '无日志')
    m = re.search(r'C ownIdx2=(\d+) ownOk=(\d)', joined)
    check('T42', '蛇数组增删后自身绑定不漂移(uid绑定)', m and m.group(2) == '1',
          m.group(0) if m else '无日志')
    m = re.search(r'C colorSame=(\d) color=(\S+)', joined)
    check('T43', '重生后颜色与自选颜色一致', m and m.group(1) == '1', m.group(0) if m else '无日志')
    m = re.search(r'jitter off\. B jitterRebases=(\d+) gaps=(\d+)', joined)
    check('T44', '网络抖动+合批投递下无重建风暴', m and int(m.group(1)) <= 4 and int(m.group(2)) <= 1,
          m.group(0) if m else '无日志')

def main():
    print('== 生成测试页(基于当前 index.html) ==')
    gen_files()
    print('== 单人测试 =='); solo_tests()
    print('== 视野公平测试 =='); view_tests()
    print('== 版本号测试 =='); version_test()
    print('== 三人联机仿真 =='); lan_tests()
    fails = [r for r in results if not r[2]]
    print('\n===== 结果: %d 项通过, %d 项失败 =====' % (len(results) - len(fails), len(fails)))
    if fails:
        print('失败项: ' + ', '.join(r[0] for r in fails))
        sys.exit(1)
    print('全部通过, 可以发布。')

if __name__ == '__main__':
    main()
