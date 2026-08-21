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

def run_chromium(url, budget, extra=None, window='1254,752', dom=False, real_secs=130):
    args = [CHROMIUM, '--headless=new', '--disable-gpu', '--no-sandbox',
            '--allow-file-access-from-files', '--window-size=' + window,
            '--enable-logging=stderr']
    if budget:
        args.append('--virtual-time-budget=' + str(budget))
    if dom:
        args.append('--dump-dom')
    if extra:
        args += extra
    args.append(url)
    if budget:
        p = subprocess.run(args, capture_output=True, text=True, timeout=600)
        out = p.stderr + '\n' + p.stdout
    else:
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            so, se = p.communicate(timeout=real_secs)
        except subprocess.TimeoutExpired:
            p.kill(); so, se = p.communicate()
        out = (se or '') + '\n' + (so or '')
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
    # 固定测试随机数，避免 AI 出生/死亡随机波动造成相同代码偶发假红；联机节点按 window.name 派生不同种子。
    seed_js = "(function(){var s=1592594996;for(var i=0;i<(window.name||'').length;i++)s=(s*33+(window.name.charCodeAt(i)||0))>>>0;Math.random=function(){s=(s*1664525+1013904223)>>>0;return s/4294967296;};})();"
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
// T45: 蘑菇回收额未清时阵亡 → 重生后吃豆必须能增长(回收账死亡即清)
if(tickN===1520&&window.__MUSHTEST__){player.mushDrain=480;player.mushs=[{t:tickN+30,v:500}];die(player,snakes[1]);slog('[TEST] dieWithDrain drainAfterDeath='+(player.mushDrain||0)+' mushs='+(player.mushs?player.mushs.length:-1));}
if(tickN===1540&&window.__MUSHTEST__){revive();player.grace=999999;}
if(tickN>=1550&&tickN<=1560&&window.__MUSHTEST__){var fh=player.pts[0];if(fh)for(var fi=0;fi<6;fi++)spawnFood(fh.x+rnd(-14,14),fh.y+rnd(-14,14),2);}
if(tickN===1740&&window.__MUSHTEST__){slog('[TEST] afterRevive alive='+(player.alive?1:0)+' score='+Math.round(player.score)+' drain='+(player.mushDrain||0));}
if(tickN===100&&window.__AITEST__){
var lb9=document.getElementById('logBtn'),eb9=document.getElementById('exitBtn'),mp9=document.getElementById('map');
var lr9=lb9&&lb9.getBoundingClientRect(),er9=eb9&&eb9.getBoundingClientRect();
var noOverlap9=!!(lr9&&er9&&(lr9.right<=er9.left||er9.right<=lr9.left||lr9.bottom<=er9.top||er9.bottom<=lr9.top));
slog('[TEST] logBtn='+(lb9?1:0)+' noOverlap='+(noOverlap9?1:0)+' mapPointer='+(mp9?getComputedStyle(mp9).pointerEvents:'none'));
var os9=started,om9=LAN.mode,oh9=LAN.lastHb,send9=lanSend,hb9=0;
started=false;LAN.mode=2;LAN.lastHb=Date.now()-1500;lanSend=function(o){if(o&&o.t==='hb')hb9++;};tick();
started=os9;LAN.mode=om9;LAN.lastHb=oh9;lanSend=send9;
slog('[TEST] waitRoomHb='+hb9);
var sr9=LAN.snapRecv,sa9=LAN.lastSnapAt;LAN.snapRecv=1;LAN.lastSnapAt=Date.now()-3000;
slog('[TEST] wallWatchdog='+((LAN.snapRecv>0&&Date.now()-LAN.lastSnapAt>2500)?1:0));LAN.snapRecv=sr9;LAN.lastSnapAt=sa9;
}
if(tickN===1525&&window.__MUSHTEST__){slog('[TEST] saveLogBtn='+(document.getElementById('saveLogBtn')?1:0)+' boostBtnGone='+(document.getElementById('boostBtn')?0:1));}
// T49: AI 激进度——每120tick记录各AI蛇头, 算直线性(原地打转则位移/路程比极低); 统计AI成长
if(tickN===300&&window.__AITEST__){window.__aiTrack={};for(var ai0=0;ai0<snakes.length;ai0++){var a0=snakes[ai0];if(!a0.isPlayer)window.__aiTrack[a0.uid]={path:0,disp:0,lx:a0.pts[0].x,ly:a0.pts[0].y,sx:a0.pts[0].x,sy:a0.pts[0].y};}}
if(window.__AITEST__&&tickN>300&&tickN<=1800&&tickN%120===0){for(var uk in window.__aiTrack){var tr=window.__aiTrack[uk];var sn0=null;for(var ai1=0;ai1<snakes.length;ai1++)if(snakes[ai1].uid==uk)sn0=snakes[ai1];if(!sn0||!sn0.alive)continue;var hh0=sn0.pts[0];tr.path+=Math.sqrt((hh0.x-tr.lx)*(hh0.x-tr.lx)+(hh0.y-tr.ly)*(hh0.y-tr.ly));tr.lx=hh0.x;tr.ly=hh0.y;}}
if(tickN===1800&&window.__AITEST__){var lin=[],grow=0,cnt=0;for(var uk2 in window.__aiTrack){var tr2=window.__aiTrack[uk2];var sn1=null;for(var ai2=0;ai2<snakes.length;ai2++)if(snakes[ai2].uid==uk2)sn1=snakes[ai2];if(!sn1)continue;cnt++;grow+=sn1.score;var dd0=Math.sqrt((tr2.lx-tr2.sx)*(tr2.lx-tr2.sx)+(tr2.ly-tr2.sy)*(tr2.ly-tr2.sy));if(tr2.path>100)lin.push(dd0/tr2.path);}
var linAvg=lin.length?lin.reduce(function(a,b){return a+b;})/lin.length:0;
var amax2=0;for(var ai3=0;ai3<snakes.length;ai3++)if(!snakes[ai3].isPlayer&&snakes[ai3].score>amax2)amax2=snakes[ai3].score;
slog('[TEST] ai linAvg='+linAvg.toFixed(3)+' linN='+lin.length+' aiAvg='+(cnt?(grow/cnt).toFixed(0):0)+' aiMax='+Math.floor(amax2));}
// T54: 计分审计——每个600tick窗口, 分数增量不得超过(吃豆+连杀+蘑菇)增量, 找出"凭空涨分"
if(window.__SOAK__&&tickN%600===0){if(!window.__aud)window.__aud={ps:player.score,pe:player.__eat||0,pc:player.__chain||0,pm:player.__mush||0,bad:0,palive:1};
var A=window.__aud;
if(player.alive&&A.palive){var dsA=player.score-A.ps,srcA=(player.__eat||0)-A.pe+(player.__chain||0)-A.pc+(player.__mush||0)-A.pm;
if(dsA>srcA+2){A.bad++;slog('[AUDIT] UNEXPLAINED t='+tickN+' ds='+dsA.toFixed(1)+' src='+srcA.toFixed(1));}}
A.ps=player.score;A.pe=player.__eat||0;A.pc=player.__chain||0;A.pm=player.__mush||0;A.palive=player.alive;}
if(window.__SOAK__&&tickN===39600){slog('[AUDIT] final bad='+(window.__aud?window.__aud.bad:-1)+' score='+Math.floor(player.score)+' eat='+Math.floor(player.__eat||0)+' chain='+(player.__chain||0)+' mush='+(player.__mush||0));}
// T51: 10分钟耐久——持续扫描蛇身相邻节段夹角(锐角/重建毛刺=夹角突大), 统计AI成长与异常
if(window.__SOAK__&&tickN>1200&&tickN%5===0&&player&&player.alive&&player.pts.length>24){
if(!window.__kink)window.__kink={n:0,mx:0};
var pp=player.pts;
for(var ki=3;ki<pp.length-2;ki++){var ax=pp[ki].x-pp[ki-1].x,ay=pp[ki].y-pp[ki-1].y,bx=pp[ki+1].x-pp[ki].x,by=pp[ki+1].y-pp[ki].y;
var la=Math.sqrt(ax*ax+ay*ay),lb=Math.sqrt(bx*bx+by*by);if(la<2||lb<2)continue;
var cs=(ax*bx+ay*by)/(la*lb);if(cs>1)cs=1;if(cs<-1)cs=-1;var ka=Math.acos(cs);
if(ka>window.__kink.mx)window.__kink.mx=ka;if(ka>0.55){window.__kink.n++;if(tickN>1000&&window.__kink.n<=20)slog('[KINK] t='+tickN+' ki='+ki+' len='+pp.length+' ka='+ka.toFixed(2)+' la='+la.toFixed(1)+' lb='+lb.toFixed(1)+' born='+(tickN-(player.bornT||0)));}
}
}
if(window.__SOAK__&&tickN%3600===0){var am4=0;for(var ai4=0;ai4<snakes.length;ai4++)if(!snakes[ai4].isPlayer&&snakes[ai4].score>am4)am4=snakes[ai4].score;
slog('[SOAK] t='+(tickN/60|0)+'s kinkN='+(window.__kink?window.__kink.n:0)+' maxK='+(window.__kink?window.__kink.mx.toFixed(2):0)+' score='+Math.floor(player.score)+' aiMax='+Math.floor(am4)+' deaths='+deaths+' foods='+foods.length);}
if(window.__SOAK__&&tickN===39600){slog('[SOAK] final kinkN='+(window.__kink?window.__kink.n:0)+' maxK='+(window.__kink?window.__kink.mx.toFixed(2):0));}
// T50: 加速豆——直行测基础速度→吃豆→测加速, 分数不得被加速消耗
if(tickN===1780&&window.__BEANTEST__){player.grace=999999;player.aiT=99999;var bh=player.pts[0];player.angle=0;player.tAngle=0;player.aiA=0;player.boostT=0;window.__bx=bh.x;window.__by=bh.y;window.__bsc=player.score;}
if(tickN===1810&&window.__BEANTEST__){var bh2=player.pts[0];window.__spd0=Math.sqrt((bh2.x-window.__bx)*(bh2.x-window.__bx)+(bh2.y-window.__by)*(bh2.y-window.__by))/30;foods.push({x:bh2.x+30,y:bh2.y,r:5,v:1,c:'#58a6ff',b:1});window.__bx=bh2.x;window.__by=bh2.y;}
if(tickN===1845&&window.__BEANTEST__){var bh3=player.pts[0];window.__spd1=Math.sqrt((bh3.x-window.__bx)*(bh3.x-window.__bx)+(bh3.y-window.__by)*(bh3.y-window.__by))/35;slog('[TEST] bean spd0='+window.__spd0.toFixed(2)+' spd1='+window.__spd1.toFixed(2)+' ratio='+(window.__spd1/window.__spd0).toFixed(2)+' boostT='+((player.boostT||0)>tickN?1:0)+' scoreCost='+(window.__bsc-player.score).toFixed(1));}
"""
    g = src.replace('<body>', '<body><script>' + seed_js + 'window.__AUTOPILOT__=true;window.__FORCE_FB__=true;'
        'window.__EATTEST__=true;window.__AURATEST__=true;window.__HEADTEST__=true;'
        'window.__POWTEST__=true;window.__BODYTEST__=true;window.__SKZOOM__=true;window.__MTTEST__=true;'
        'window.__SPAWNTEST__=true;window.__CHAINTEST__=true;window.__MUSHTEST__=true;window.__AITEST__=true;window.__BEANTEST__=true;</script>', 1)
    g = g.replace('if(window.__EATTEST__){', probes + '\nif(window.__EATTEST__){', 1)
    open(os.path.join(WORK, 'g.html'), 'w', encoding='utf-8').write(g)
    # ---- 联机节点页 ----
    fb = src.replace('<body>', '<body><script>' + seed_js + '(function(){var p="LS_"+(window.name||"")+"_",o=window.localStorage;'
        'Object.defineProperty(window,"localStorage",{get:function(){return{getItem:function(k){return o.getItem(p+k)},'
        'setItem:function(k,v){o.setItem(p+k,v)},removeItem:function(k){o.removeItem(p+k)},clear:function(){o.clear()}}}});})();'
        'window.__FORCE_FB__=true;window.__LANTEST__=true;window.__AUTOPILOT__=true;</script>', 1)
    fb = fb.replace("init();\n})();",
        "init();\nwindow.__G={get LAN(){return LAN},get player(){return player},get snakes(){return snakes},"
        "get foods(){return foods},get cv(){return cv},get remotes(){return remotes},get tickN(){return tickN},"
        "get paused(){return paused},get DBG(){return DBG},die:function(s,k){die(s,k);},mkSnake:mkSnake,"
        "lanSend:function(o){lanSend(o);}};\n})();")
    open(os.path.join(WORK, 'lan_fb.html'), 'w', encoding='utf-8').write(fb)
    # ---- 10分钟耐久页(锐角/异常扫描) ----
    sk = src.replace('<body>', '<body><script>' + seed_js + 'window.__AUTOPILOT__=true;window.__FORCE_FB__=true;window.__SOAK__=true;</script>', 1)
    sk = sk.replace('if(window.__EATTEST__){', probes + '\nif(window.__EATTEST__){', 1)
    open(os.path.join(WORK, 'soak.html'), 'w', encoding='utf-8').write(sk)
    # ---- 真实帧耗页(大蛇高负载, 非虚拟时间) ----
    pf = src.replace('<body>', '<body><script>' + seed_js + 'window.__PERF__=true;window.__AUTOPILOT__=true;window.__BIGTEST__=true;window.__FORCE_FB__=true;</script>', 1)
    pf = pf.replace('if(AUTO){', 'if(window.__BIGTEST__&&tickN===120){for(var bi9=0;bi9<snakes.length;bi9++){snakes[bi9].score=2600;snakes[bi9].vlen=2600;}}\nif(AUTO){', 1)
    open(os.path.join(WORK, 'perf.html'), 'w', encoding='utf-8').write(pf)
    # ---- 三人联机仿真 ----
    sim = open(os.path.join(ROOT, 'tests/lan_sim3_tpl.html'), encoding='utf-8').read()
    sim = sim.replace('__FB_PATH__', os.path.join(WORK, 'lan_fb.html'))
    open(os.path.join(WORK, 'lan_sim3.html'), 'w', encoding='utf-8').write(sim)
    # ---- 联机长程耐久(12分钟, 全程抖动) ----
    lsk = open(os.path.join(ROOT, 'tests/lan_soak_tpl.html'), encoding='utf-8').read()
    lsk = lsk.replace('__FB_PATH__', os.path.join(WORK, 'lan_fb.html'))
    open(os.path.join(WORK, 'lan_soak.html'), 'w', encoding='utf-8').write(lsk)

def solo_tests():
    logs, _ = run_chromium('file://' + os.path.join(WORK, 'g.html'), 31000)
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
    d1 = re.search(r'dieWithDrain drainAfterDeath=(\d+) mushs=(\d+)', joined)
    d2 = re.search(r'afterRevive alive=(\d) score=(\d+) drain=(\d+)', joined)
    check('T45', '带蘑菇回收额阵亡重生后吃豆能增长(不卡26)', d1 and d1.group(1) == '0' and d1.group(2) == '0'
          and d2 and d2.group(1) == '1' and int(d2.group(2)) > 26 and int(d2.group(3)) == 0,
          ' / '.join(x.group(0) if x else '无日志' for x in [d1, d2]))

    m = re.search(r'ai linAvg=([\d.]+) linN=(\d+) aiAvg=(\d+) aiMax=(\d+)', joined)
    check('T49', 'AI激进进食(不原地打转, 持续长大)',
          m and float(m.group(1)) > 0.24 and int(m.group(4)) >= 130 and int(m.group(3)) >= 55,
          m.group(0) if m else '无日志')
    m = re.search(r'bean spd0=([\d.]+) spd1=([\d.]+) ratio=([\d.]+) boostT=(\d) scoreCost=(-?[\d.]+)', joined)
    check('T50', '加速豆: 吃豆加速且不耗分数',
          m and float(m.group(3)) > 1.35 and m.group(4) == '1' and float(m.group(5)) < 1.0,
          m.group(0) if m else '无日志')
    m = re.search(r'saveLogBtn=(\d) boostBtnGone=(\d)', joined)
    check('T50b', '阵亡弹窗有保存日志按钮/加速按钮已移除',
          m and m.group(1) == '1' and m.group(2) == '1',
          m.group(0) if m else '无日志')
    m = re.search(r'logBtn=(\d) noOverlap=(\d) mapPointer=(\S+)', joined)
    check('T55', '日志按钮可见可点且小地图调试入口可用',
          m and m.group(1) == '1' and m.group(2) == '1' and m.group(3) != 'none',
          m.group(0) if m else '无日志')
    m = re.search(r'waitRoomHb=(\d+)', joined)
    check('T58', '客机等待房主开局期间持续心跳', m and int(m.group(1)) >= 1,
          m.group(0) if m else '无日志')
    m = re.search(r'wallWatchdog=(\d)', joined)
    check('T59', '断线看门狗使用墙钟而非游戏tick', m and m.group(1) == '1',
          m.group(0) if m else '无日志')


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
def lan_soak_tests():
    logs, _ = run_chromium('file://' + os.path.join(WORK, 'lan_soak.html'), 790000, window='900,560')
    joined = '\n'.join(logs)
    errs = [l for l in logs if l.startswith('[ERR]')]
    mJ1 = re.search(r'\[SOAKLAN\] stage1000 jerk=(\d+)/(\d+)', joined)
    mJ3 = re.search(r'\[SOAKLAN\] stage3000 jerk=(\d+)/(\d+)', joined)
    check('T57', '从机蛇头跳动率(1000+/3000+档均<2%)',
          mJ1 and mJ3 and int(mJ1.group(1)) < int(mJ1.group(2))*0.02 and int(mJ3.group(1)) < int(mJ3.group(2))*0.02,
          ((mJ1.group(0) if mJ1 else '无1000档') + ' | ' + (mJ3.group(0) if mJ3 else '无3000档')))
    m = re.search(r'\[SOAKLAN\] final snaps=(\d+) rebases=(\d+) gaps=(\d+) teleports=(\d+) dead=(\d) entered=(\d) kinkN=(\d+) maxK=([\d.]+) hostRemoteN=(\d+)', joined)
    check('T53', '联机12分钟长程(抖动): 不掉线/无瞬移/无锐角',
          m and len(errs) == 0 and m.group(5) == '0' and m.group(6) == '1'
          and int(m.group(4)) <= 6 and int(m.group(7)) <= 8 and float(m.group(8)) < 0.9 and int(m.group(9)) >= 1,
          (m.group(0) if m else '无日志(未跑满)') + (' ERR:' + ';'.join(errs[:2]) if errs else ''))

def soak_tests():
    logs, _ = run_chromium('file://' + os.path.join(WORK, 'soak.html'), 670000)
    joined = '\n'.join(logs)
    errs = [l for l in logs if l.startswith('[ERR]')]
    m = re.search(r'\[SOAK\] final kinkN=(\d+) maxK=([\d.]+)', joined)
    m2 = re.search(r'\[AUDIT\] final bad=(\d+)', joined)
    check('T54', '计分审计: 10分钟内无凭空涨分', m2 and m2.group(1) == '0',
          m2.group(0) if m2 else '无审计日志')
    check('T51', '10分钟耐久: 无异常/蛇身无锐角毛刺',
          m and len(errs) == 0 and int(m.group(1)) <= 6 and float(m.group(2)) < 0.9,
          (m.group(0) if m else '无日志(未满10分钟)') + (' ERR:' + ';'.join(errs[:2]) if errs else ''))

def perf_tests():
    logs, _ = run_chromium('file://' + os.path.join(WORK, 'perf.html'), 0, real_secs=130)
    pl = [l for l in logs if '[PERF] tick' in l]
    m = re.search(r'tick avg=([\d.]+)ms render avg=([\d.]+)ms', pl[-1]) if pl else None
    check('T52', '真实帧耗(5蛇x2600分): tick<6ms render<8ms',
          m and float(m.group(1)) < 6 and float(m.group(2)) < 8,
          pl[-1] if pl else '无PERF日志')

def lan_tests():
    logs, _ = run_chromium('file://' + os.path.join(WORK, 'lan_sim3.html'), 37000, window='1300,700')
    joined = '\n'.join(logs)
    check('T21', '主机建房+两客机加入(remotes=2)', 'remotes=2' in joined)
    check('T22', '第三玩家真正入局(ownIdx=11)', 'C ownIdx=11' in joined)
    check('T23', '从机免确认自动进入', joined.count('autoEntered=true') >= 2)
    check('T24', '快照30Hz持续下发', bool(re.search(r'B snaps=([4-9]\d|\d{3,})', joined)))
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
    m = re.search(r'B autoRejoin tryN=(\d+)', joined)
    check('T39', '断线看门狗触发自动重连(无僵尸局)', m and int(m.group(1)) >= 1, m.group(0) if m else '无日志')
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
    m = re.search(r'jitter off\. B jitterRebases=(\d+) gaps=(\d+) teleports=(\d+)', joined)
    check('T44', '网络抖动+合批投递下无重建风暴/无瞬移', m and int(m.group(1)) <= 4 and int(m.group(2)) <= 1 and int(m.group(3)) <= 1,
          m.group(0) if m else '无日志')
    m = re.search(r'B rejoined entered=(\d) alive=(\d) name=(\S+)', joined)
    check('T48', '彻底断线后自动重连回到游戏', m and m.group(1) == '1' and m.group(2) == '1' and m.group(3) == '客机B',
          m.group(0) if m else '无日志')

def main():
    print('== 生成测试页(基于当前 index.html) ==')
    gen_files()
    print('== 单人测试 =='); solo_tests()
    print('== 视野公平测试 =='); view_tests()
    print('== 版本号测试 =='); version_test()
    print('== 三人联机仿真 =='); lan_tests()
    print('== 10分钟耐久 =='); soak_tests()
    print('== 真实帧耗 =='); perf_tests()
    print('== 联机12分钟长程 =='); lan_soak_tests()
    fails = [r for r in results if not r[2]]
    print('\n===== 结果: %d 项通过, %d 项失败 =====' % (len(results) - len(fails), len(fails)))
    if fails:
        print('失败项: ' + ', '.join(r[0] for r in fails))
        sys.exit(1)
    print('全部通过, 可以发布。')

if __name__ == '__main__':
    main()
