"""
Spike PyWebView: valida que (1) abre ventana con HTML/CSS moderno y
(2) el puente JS -> Python funciona en esta máquina (WebView2).
Correr:  python spike/hello_webview.py
"""
import webview


class Api:
    def saludar(self, nombre):
        return f"Hola {nombre} — Python respondió por el puente."


HTML = """
<!DOCTYPE html>
<html><body style="background:#0c0c10;color:#e8e8e8;font-family:Segoe UI,sans-serif;
display:flex;flex-direction:column;align-items:center;justify-content:center;
height:95vh;margin:0;gap:18px">
  <h1 style="font-weight:600;margin:0">
    <span style="color:#e8ff00">Bel</span><span style="color:#ff3c6e">App</span>
    <span style="color:#9a9aa8;font-size:15px;font-weight:400"> spike</span>
  </h1>
  <button style="padding:11px 26px;border-radius:999px;border:none;background:#e8ff00;
   color:#0c0c10;font-weight:600;font-size:14px;cursor:pointer"
   onclick="pywebview.api.saludar('Bel').then(r => document.getElementById('out').innerText = r)">
    Probar puente JS → Python
  </button>
  <p id="out" style="color:#00ffa3;font-size:14px;min-height:20px"></p>
</body></html>
"""

if __name__ == '__main__':
    webview.create_window('BelApp — spike PyWebView', html=HTML,
                          js_api=Api(), width=540, height=400)
    webview.start()
