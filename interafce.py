"""
Motor 3 + AS5600  —  веб-интерфейс
pip install flask pyserial
python motor3_web.py  →  http://localhost:5000
"""

import serial, serial.tools.list_ports
import threading, time
from flask import Flask, request, jsonify, render_template_string

# ── Порт ─────────────────────────────────────────────────────
def find_port():
    for p in serial.tools.list_ports.comports():
        desc = (p.description or "").upper()
        if any(x in desc for x in ["ARDUINO", "CH340", "CP210", "UART"]):
            return p.device
    return None

PORT = find_port() or "COM3"   # поменяй если не найдёт
BAUD = 115200

# ── Глобальное состояние ──────────────────────────────────────
state = {
    "angle":      -1.0,
    "raw":        -1,
    "calibrated": False,
    "magnet":     False,
    "targeting":  False,
    "log":        [],
    "connected":  False,
}

ser      = None
ser_lock = threading.Lock()

def log_add(msg):
    state["log"].append(msg)
    if len(state["log"]) > 120:
        state["log"].pop(0)

def send(cmd: str):
    if ser and ser.is_open:
        with ser_lock:
            try:
                ser.write((cmd + "\n").encode())
                log_add("-> " + cmd)
            except Exception as e:
                log_add(f"SEND ERR: {e}")

def parse(line: str):
    log_add("<- " + line)
    if line.startswith("ANG:"):
        p = {}
        for part in line.split():
            if ":" in part:
                k, v = part.split(":", 1)
                p[k] = v
        try: state["angle"]      = float(p.get("ANG", -1))
        except: pass
        try: state["raw"]        = int(p.get("RAW", -1))
        except: pass
        state["calibrated"] = p.get("CAL", "0") == "1"
        state["magnet"]     = p.get("MAG", "0") == "1"
        state["targeting"]  = p.get("TGT", "0") == "1"
    elif line.startswith("AT:"):
        state["targeting"] = False
        try: state["angle"] = float(line[3:])
        except: pass
    elif line == "STOP":
        state["targeting"] = False
    elif line.startswith("CAL_OK:"):
        state["calibrated"] = True

def serial_reader():
    while True:
        try:
            if not (ser and ser.is_open):
                time.sleep(0.5); continue
            with ser_lock:
                avail = ser.in_waiting
            if avail:
                with ser_lock:
                    line = ser.readline().decode(errors="replace").strip()
                if line:
                    parse(line)
            else:
                time.sleep(0.01)
        except Exception as e:
            log_add(f"READ ERR: {e}")
            time.sleep(0.5)

def poller():
    time.sleep(2)
    while True:
        send("STATUS")
        time.sleep(0.2)

HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Motor 3 AS5600</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Bebas+Neue&display=swap');
:root{
  --bg:#080a0f;--card:#0e1118;--border:#1a2030;
  --cyan:#00f5d4;--orange:#ff6b35;--green:#39ff14;
  --dim:#2a3348;--text:#8899bb;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'JetBrains Mono',monospace;
  min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:20px 12px}
h1{font-family:'Bebas Neue',sans-serif;font-size:2rem;letter-spacing:6px;
  color:var(--cyan);text-shadow:0 0 30px rgba(0,245,212,.35);margin-bottom:20px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;width:100%;max-width:580px}
@media(max-width:520px){.grid{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px}
.card h2{font-size:.6rem;letter-spacing:4px;text-transform:uppercase;color:var(--dim);margin-bottom:14px}
.gauge-wrap{display:flex;flex-direction:column;align-items:center}
.angle-num{font-family:'Bebas Neue',sans-serif;font-size:3.2rem;
  color:var(--cyan);text-shadow:0 0 40px rgba(0,245,212,.5);line-height:1;margin-top:6px}
.angle-raw{font-size:.7rem;color:var(--dim);margin-top:3px}
.pills{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap;justify-content:center}
.pill{font-size:.55rem;letter-spacing:2px;padding:3px 10px;border-radius:20px;
  border:1px solid var(--dim);color:var(--dim);transition:all .25s}
.pill.on{border-color:var(--green);color:var(--green);box-shadow:0 0 8px rgba(57,255,20,.25)}
.pill.blink{border-color:var(--orange);color:var(--orange);animation:blink .5s step-end infinite}
@keyframes blink{50%{opacity:0}}
.btn{width:100%;padding:11px 8px;border:1px solid var(--border);border-radius:6px;
  background:transparent;color:var(--text);font-family:'JetBrains Mono',monospace;
  font-size:.8rem;letter-spacing:1px;cursor:pointer;transition:all .15s;
  text-transform:uppercase;margin-bottom:7px}
.btn:hover{border-color:var(--cyan);color:var(--cyan);background:rgba(0,245,212,.04)}
.btn:active{transform:scale(.97)}
.btn.c{border-color:var(--cyan);color:var(--cyan)}
.btn.g{border-color:var(--green);color:var(--green)}
.btn.r{border-color:var(--orange);color:var(--orange)}
.row{display:flex;gap:7px;margin-bottom:7px}
.row .btn{margin-bottom:0}
.irow{display:flex;gap:7px;margin-top:10px}
input[type=number]{flex:1;background:var(--bg);border:1px solid var(--border);
  border-radius:6px;color:var(--cyan);font-family:'JetBrains Mono',monospace;
  font-size:1.1rem;padding:9px 12px;outline:none}
input[type=number]:focus{border-color:var(--cyan)}
.presets{display:flex;gap:5px;margin-top:8px;flex-wrap:wrap}
.pb{flex:1;min-width:44px;padding:6px 2px;background:transparent;
  border:1px solid var(--dim);border-radius:4px;color:var(--dim);
  font-family:'JetBrains Mono',monospace;font-size:.75rem;cursor:pointer;transition:all .2s}
.pb:hover{border-color:var(--cyan);color:var(--cyan)}
input[type=range]{width:100%;accent-color:var(--cyan);margin:6px 0}
.sv{font-size:.75rem;color:var(--cyan);text-align:right}
.log-card{grid-column:span 2}
@media(max-width:520px){.log-card{grid-column:span 1}}
#log{background:var(--bg);border:1px solid var(--border);border-radius:6px;
  height:120px;overflow-y:auto;padding:8px 10px;font-size:.65rem}
#log .tx{color:#1a5c6e}#log .rx{color:#2a5e2a}
.dot{width:7px;height:7px;border-radius:50%;background:var(--orange);
  display:inline-block;margin-right:6px;vertical-align:middle;transition:background .3s}
.dot.ok{background:var(--green);box-shadow:0 0 6px var(--green)}
</style>
</head>
<body>
<h1>MOTOR 3 / AS5600</h1>
<div class="grid">

  <div class="card gauge-wrap">
    <h2>Encoder Position</h2>
    <canvas id="g" width="190" height="190"></canvas>
    <div class="angle-num" id="anum">---</div>
    <div class="angle-raw" id="araw">RAW: ---</div>
    <div class="pills">
      <span class="pill" id="pMag">MAGNET</span>
      <span class="pill" id="pCal">CALIBRATED</span>
      <span class="pill" id="pTgt">TARGETING</span>
    </div>
    <div style="margin-top:10px;font-size:.6rem">
      <span class="dot" id="dot"></span>
      <span id="ctxt">connecting...</span>
    </div>
  </div>

  <div class="card">
    <h2>Control</h2>
    <button class="btn g" onclick="cmd('CAL')">Set Zero Here</button>
    <div class="row">
      <button class="btn"
        onmousedown="hold('U')" onmouseup="cmd('X')"
        ontouchstart="hold('U')" ontouchend="cmd('X')">CW</button>
      <button class="btn"
        onmousedown="hold('D')" onmouseup="cmd('X')"
        ontouchstart="hold('D')" ontouchend="cmd('X')">CCW</button>
    </div>
    <button class="btn r" onclick="cmd('X')">STOP</button>
    <div style="margin-top:12px">
      <div style="font-size:.55rem;letter-spacing:3px;color:var(--dim);margin-bottom:4px">GOTO ANGLE</div>
      <div class="irow">
        <input type="number" id="gt" value="90" min="0" max="359" step="1">
        <button class="btn c" style="width:auto;padding:9px 14px;margin:0" onclick="gotoAngle()">GO</button>
      </div>
      <div class="presets">
        <button class="pb" onclick="go(0)">0</button>
        <button class="pb" onclick="go(45)">45</button>
        <button class="pb" onclick="go(90)">90</button>
        <button class="pb" onclick="go(180)">180</button>
        <button class="pb" onclick="go(270)">270</button>
      </div>
    </div>
    <div style="margin-top:14px">
      <div style="font-size:.55rem;letter-spacing:3px;color:var(--dim)">SPEED (delay µs)</div>
      <input type="range" id="spd" min="200" max="3000" value="800" oninput="setSpeed(this.value)">
      <div class="sv" id="spdv">800 µs</div>
    </div>
  </div>

  <div class="card log-card">
    <h2>Serial Log</h2>
    <div id="log"></div>
  </div>

</div>
<script>
let holdTimer=null, logCount=0;
async function cmd(c){
  await fetch('/cmd',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd:c})});
}
function hold(dir){cmd(dir);holdTimer=setInterval(()=>cmd(dir),100);}
document.addEventListener('mouseup',()=>{if(holdTimer){clearInterval(holdTimer);holdTimer=null;}});
document.addEventListener('touchend',()=>{if(holdTimer){clearInterval(holdTimer);holdTimer=null;}});
function gotoAngle(){const v=parseFloat(document.getElementById('gt').value);if(!isNaN(v))cmd('GOTO:'+v.toFixed(1));}
function go(a){document.getElementById('gt').value=a;cmd('GOTO:'+a+'.0');}
function setSpeed(v){document.getElementById('spdv').textContent=v+' µs';cmd('SPEED:'+v);}

const cv=document.getElementById('g');const c2=cv.getContext('2d');
const CX=95,CY=95,R=72;
function drawGauge(a){
  c2.clearRect(0,0,190,190);
  c2.beginPath();c2.arc(CX,CY,R,0,Math.PI*2);c2.strokeStyle='#1a2030';c2.lineWidth=10;c2.stroke();
  for(let i=0;i<36;i++){
    const ang=-Math.PI/2+(i/36)*Math.PI*2;
    const r0=i%9===0?R+8:R+4;
    c2.beginPath();
    c2.moveTo(CX+(R+2)*Math.cos(ang),CY+(R+2)*Math.sin(ang));
    c2.lineTo(CX+r0*Math.cos(ang),CY+r0*Math.sin(ang));
    c2.strokeStyle=i%9===0?'#2a3a4a':'#161d2a';c2.lineWidth=i%9===0?2:1;c2.stroke();
  }
  if(a===null||a<0)return;
  const end=-Math.PI/2+(a/360)*Math.PI*2;
  c2.beginPath();c2.arc(CX,CY,R,-Math.PI/2,end);
  c2.strokeStyle='#00f5d4';c2.lineWidth=10;c2.lineCap='round';c2.stroke();
  c2.beginPath();c2.arc(CX+R*Math.cos(end),CY+R*Math.sin(end),7,0,Math.PI*2);
  c2.fillStyle='#00f5d4';c2.shadowBlur=20;c2.shadowColor='#00f5d4';c2.fill();c2.shadowBlur=0;
}
drawGauge(null);

async function poll(){
  try{
    const r=await fetch('/state');const d=await r.json();
    drawGauge(d.angle>=0?d.angle:null);
    document.getElementById('anum').textContent=d.angle>=0?d.angle.toFixed(1)+'°':'---';
    document.getElementById('araw').textContent='RAW: '+(d.raw>=0?d.raw:'---');
    function pill(id,on,warn){const e=document.getElementById(id);e.classList.remove('on','blink');if(on)e.classList.add(warn?'blink':'on');}
    pill('pMag',d.magnet,false);pill('pCal',d.calibrated,false);pill('pTgt',d.targeting,true);
    document.getElementById('dot').classList.toggle('ok',d.connected);
    document.getElementById('ctxt').textContent=d.connected?'connected':'no serial';
    const lb=document.getElementById('log');
    if(d.log.length>logCount){
      d.log.slice(logCount).forEach(l=>{
        const el=document.createElement('div');
        el.className=l.startsWith('->')?'tx':'rx';
        el.textContent=l;lb.appendChild(el);
      });
      logCount=d.log.length;lb.scrollTop=lb.scrollHeight;
    }
  }catch(e){}
  setTimeout(poll,250);
}
poll();
</script>
</body>
</html>"""

app = Flask(__name__)

@app.route("/")
def index(): return render_template_string(HTML)

@app.route("/cmd", methods=["POST"])
def do_cmd():
    c = (request.get_json() or {}).get("cmd","").strip()
    if c: send(c)
    return jsonify(ok=True)

@app.route("/state")
def get_state(): return jsonify(**state)

if __name__ == "__main__":
    print(f"Порт: {PORT}")
    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.1)
        time.sleep(2)
        state["connected"] = True
        print("Arduino подключена!")
    except Exception as e:
        print(f"Ошибка порта: {e}")
        print("Запускаю без Serial — поменяй PORT в коде")
    threading.Thread(target=serial_reader, daemon=True).start()
    threading.Thread(target=poller, daemon=True).start()
    print("\nОткрой: http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=False)