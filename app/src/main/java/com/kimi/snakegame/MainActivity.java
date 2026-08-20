package com.kimi.snakegame;

import android.app.Activity;
import android.content.Context;
import android.net.wifi.WifiManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.concurrent.LinkedBlockingQueue;

public class MainActivity extends Activity {
    private WebView wv;
    private final Handler ui = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        wv = new WebView(this);
        WebSettings st = wv.getSettings();
        st.setJavaScriptEnabled(true);
        st.setDomStorageEnabled(true);
        wv.setOverScrollMode(View.OVER_SCROLL_NEVER);
        wv.addJavascriptInterface(new Bridge(), "Android");
        setContentView(wv);
        wv.loadUrl("file:///android_asset/index.html");
        hideUI();
    }

    class Bridge {
        private ServerSocket ss;
        private volatile boolean running;
        private final java.util.concurrent.ConcurrentHashMap<Integer, ClientConn> clients = new java.util.concurrent.ConcurrentHashMap<>();
        private int nextId = 1;
        // 客机模式（join）单连接
        private ClientConn server;

        private class ClientConn {
            final Socket sock;
            final PrintWriter out;
            final LinkedBlockingQueue<String> sendQ = new LinkedBlockingQueue<>(256);
            final StringBuilder pend = new StringBuilder();
            volatile boolean posted = false;
            volatile boolean alive = true;

            ClientConn(Socket s) throws Exception {
                sock = s;
                out = new PrintWriter(new OutputStreamWriter(s.getOutputStream(), "UTF-8"), false);
            }

            int drops = 0;

            void startSender() {
                Thread t = new Thread(() -> {
                    try {
                        while (alive && running) {
                            String m = sendQ.take();
                            synchronized (out) {
                                out.print(m);
                                out.print('\n');
                                out.flush();
                                // PrintWriter 出错不抛异常, 必须主动检查, 否则半开连接永远"发送成功"
                                if (out.checkError()) { netLog("write error, closing"); break; }
                            }
                        }
                    } catch (Exception e) { netLog("sender err " + e.getMessage()); }
                    close();
                });
                t.setDaemon(true);
                t.start();
            }

            void send(String msg) {
                if (!alive) return;
                // 队列满时丢弃最旧消息，保最新（快照类消息新覆盖旧，避免延迟堆积）
                while (!sendQ.offer(msg)) {
                    sendQ.poll();
                    if (++drops % 100 == 1) netLog("sendQ drops=" + drops);
                }
            }

            void close() {
                alive = false;
                try { sock.close(); } catch (Exception ignored) {}
            }
        }

        @JavascriptInterface
        public void exitApp() {
            ui.post(() -> { lanStop(); finish(); });
        }

        @JavascriptInterface
        public String saveLog(final String text) {
            try {
                java.io.File dir = getExternalFilesDir(null);
                if (dir == null) dir = getFilesDir();
                String name = "snake_log_" + new java.text.SimpleDateFormat("yyyyMMdd_HHmmss", java.util.Locale.US).format(new java.util.Date()) + ".txt";
                java.io.File f = new java.io.File(dir, name);
                java.io.FileOutputStream fos = new java.io.FileOutputStream(f);
                fos.write(text.getBytes("UTF-8"));
                fos.close();
                final String path = f.getAbsolutePath();
                ui.post(() -> android.widget.Toast.makeText(MainActivity.this, "日志已保存: " + path, android.widget.Toast.LENGTH_LONG).show());
                return path;
            } catch (Exception e) {
                return "保存失败: " + e.getMessage();
            }
        }

        @JavascriptInterface
        public void lanHost(final int port) {
            lanStop();
            running = true;
            new Thread(() -> {
                try {
                    ss = new ServerSocket(port);
                    status("listening ip=" + localIp());
                    while (running) {
                        Socket s = ss.accept();
                        s.setTcpNoDelay(true);
                        // 5秒读超时: 客机每秒有心跳, 10秒无上行即为半开死连接
                        s.setSoTimeout(10000);
                        final int id = nextId++;
                        netLog("accept id=" + id);
                        try {
                            final ClientConn c = new ClientConn(s);
                            clients.put(id, c);
                            c.startSender();
                            peer(id, true);
                            status("connected");
                            new Thread(() -> readLoop(id, c)).start();
                        } catch (Exception e) {
                            try { s.close(); } catch (Exception ignored) {}
                        }
                    }
                } catch (Exception e) {
                    if (running) status("error " + e.getMessage());
                }
            }).start();
        }

        @JavascriptInterface
        public void lanJoin(final String ip, final int port) {
            lanStop();
            running = true;
            new Thread(() -> {
                try {
                    Socket s = new Socket();
                    s.connect(new InetSocketAddress(ip, port), 6000);
                    s.setTcpNoDelay(true);
                    final ClientConn c = new ClientConn(s);
                    server = c;
                    c.startSender();
                    status("connected");
                    readLoop(0, c);
                } catch (Exception e) {
                    if (running) status("error " + e.getMessage());
                }
            }).start();
        }

        private void readLoop(int id, ClientConn c) {
            String why = "eof";
            try {
                BufferedReader br = new BufferedReader(new InputStreamReader(c.sock.getInputStream(), "UTF-8"));
                String line;
                while (running && c.alive && (line = br.readLine()) != null) {
                    // 有界缓冲+合批: 每行本身是完整JSON对象, 直接拼进待注入缓冲区;
                    // UI线程未消化时不新排队(只追加到同一批次), 背压自动转合批, 消息永不无限堆积
                    // (无界ui.post队列曾让从机渲染越来越旧的快照→卡顿/瞬移/超时掉线)
                    synchronized (c.pend) {
                        if (c.pend.length() > 0) c.pend.append(',');
                        c.pend.append(line);
                        int bn = 1;
                        while (bn < 64 && br.ready()) {
                            String more = br.readLine();
                            if (more == null) break;
                            c.pend.append(',').append(more);
                            bn++;
                        }
                    }
                    if (!c.posted) {
                        c.posted = true;
                        ui.post(() -> {
                            String body;
                            synchronized (c.pend) { body = c.pend.toString(); c.pend.setLength(0); }
                            c.posted = false;
                            wv.evaluateJavascript("window.__lanOnMsgs(" + id + ",[" + body + "])", null);
                        });
                    }
                }
            } catch (Exception e) { why = String.valueOf(e.getMessage()); }
            netLog("read end id=" + id + " why=" + why);
            if (id > 0) {
                clients.remove(id);
                peer(id, false);
            } else {
                status("closed");
            }
            c.close();
        }

        private void netLog(String s) {
            final String js = "if(window.__lanLog)window.__lanLog(" + JSONObject.quote(s) + ")";
            ui.post(() -> wv.evaluateJavascript(js, null));
        }

        @JavascriptInterface
        public void lanSend(final String msg) {
            ClientConn sv = server;
            if (sv != null) { sv.send(msg); return; }
            for (ClientConn c : clients.values()) c.send(msg);
        }

        @JavascriptInterface
        public void lanSendTo(final int id, final String msg) {
            ClientConn c = clients.get(id);
            if (c != null) c.send(msg);
        }

        @JavascriptInterface
        public void lanStop() {
            running = false;
            try { if (ss != null) ss.close(); } catch (Exception ignored) {}
            ss = null;
            for (ClientConn c : clients.values()) c.close();
            clients.clear();
            if (server != null) { server.close(); server = null; }
        }

        private void peer(int id, boolean joined) {
            final String js = "window.__lanPeer(" + id + "," + joined + ")";
            ui.post(() -> wv.evaluateJavascript(js, null));
        }

        private void status(String s) {
            final String js = "window.__lanStatus(" + JSONObject.quote(s) + ")";
            ui.post(() -> wv.evaluateJavascript(js, null));
        }

        private String localIp() {
            try {
                WifiManager wm = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
                int ip = wm.getConnectionInfo().getIpAddress();
                return (ip & 0xff) + "." + ((ip >> 8) & 0xff) + "." + ((ip >> 16) & 0xff) + "." + ((ip >> 24) & 0xff);
            } catch (Exception e) {
                return "未知";
            }
        }
    }

    private void hideUI() {
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) hideUI();
    }

    @Override
    public void onBackPressed() {
        moveTaskToBack(true);
    }
}
