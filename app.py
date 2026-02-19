

# app.py
import os, json, traceback
from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
import sqlite3
from reportlab.pdfgen import canvas
from io import BytesIO

# Optional GPT4All
try:
    from gpt4all import GPT4All
    GPT4ALL_AVAILABLE = True
except Exception:
    GPT4ALL_AVAILABLE = False

# Serve static files from ./static and templates from ./templates
app = Flask(__name__, static_folder="static", template_folder="templates", static_url_path="/static")
CORS(app)  # not strictly necessary for same-origin, but harmless

BASE = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE, 'database.db')

# Simple rules
RULES = {
    'fever': 'Flu',
    'rash': 'Dengue',
    'cough': 'Common Cold / COVID-19',
    'nausea': 'Food Poisoning',
    'thirst': 'Diabetes',
    'loss smell': 'COVID-19'
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symptoms TEXT,
                    prediction TEXT,
                    advice TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit(); conn.close()
init_db()

# Optional LLM model object
gpt_model = None
if GPT4ALL_AVAILABLE:
    try:
        gpt_model = GPT4All(model='ggml-gpt4all-j-v1.3-groovy')
    except Exception as e:
        print('Could not initialize GPT4All:', e)
        gpt_model = None

def rule_predict(text):
    txt = text.lower()
    scores = {}
    for k,v in RULES.items():
        if k in txt:
            scores[v] = scores.get(v,0) + 1
    if not scores:
        return [{'label':'General Infection', 'prob':0.4}, {'label':'Allergy', 'prob':0.2}]
    items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    out = [{'label':items[0][0], 'prob':0.8}]
    for it in items[1:3]:
        out.append({'label':it[0], 'prob':0.5})
    return out

# Serve the frontend
@app.route('/')
def index():
    return render_template('index.html')

# API endpoints (same as before)
@app.route('/api/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json() or {}
        symptoms = data.get('symptoms','').strip()
        if not symptoms:
            return jsonify({'error':'No symptoms provided'}), 400
        preds = rule_predict(symptoms)
        advice = 'This is a preliminary suggestion. For accurate diagnosis consult a physician.'
        conn = sqlite3.connect(DB_PATH); c=conn.cursor()
        c.execute("INSERT INTO history (symptoms, prediction, advice) VALUES (?,?,?)", (symptoms, json.dumps(preds), advice))
        conn.commit(); conn.close()
        return jsonify({'predictions': preds, 'advice': advice})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json() or {}
        msg = data.get('message','').strip()
        if not msg:
            return jsonify({'error':'No message provided'}), 400
        if gpt_model:
            try:
                resp = gpt_model.generate(msg, max_tokens=200)
                if isinstance(resp, (list,tuple)):
                    ans = resp[0]
                else:
                    ans = str(resp)
            except Exception as e:
                ans = f'[LLM error] {e}'
        else:
            ml = msg.lower()
            if 'fever' in ml:
                ans = 'Fever can be managed with rest and fluids. If >103F or persistent, see a doctor.'
            elif 'hospital' in ml or 'emergency' in ml:
                ans = 'If emergency, call local emergency services. For hospital search use the Hospital Finder.'
            else:
                ans = 'I am an assistant. Describe your symptoms in detail; this is not a medical diagnosis.'
        return jsonify({'answer': ans})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/history', methods=['GET'])
def history():
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute('SELECT id, symptoms, prediction, advice, created_at FROM history ORDER BY created_at DESC')
    rows = c.fetchall(); conn.close()
    out = []
    for r in rows:
        try:
            pred = json.loads(r[2]) if r[2] else None
        except:
            pred = r[2]
        out.append({'id':r[0],'symptoms':r[1],'prediction':pred,'advice':r[3],'created_at':r[4]})
    return jsonify(out)

@app.route('/api/report/<int:hid>', methods=['GET'])
def report(hid):
    conn = sqlite3.connect(DB_PATH); c=conn.cursor()
    c.execute('SELECT id, symptoms, prediction, advice, created_at FROM history WHERE id=?', (hid,))
    row = c.fetchone(); conn.close()
    if not row:
        return jsonify({'error':'Not found'}), 404
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=(595,842))
    p.setFont('Helvetica-Bold', 16); p.drawString(40,800,'Smart Health Assistant - Report')
    p.setFont('Helvetica',11); p.drawString(40,770, f'Record ID: {row[0]}'); p.drawString(40,750, f'Date: {row[4]}')
    p.drawString(40,730, 'Symptoms:'); p.drawString(60,715, row[1])
    p.drawString(40,690, 'Predictions:')
    y=670
    try:
        preds = json.loads(row[2])
    except:
        preds = []
    for it in preds:
        try:
            p.drawString(60,y, f"- {it.get('label')} ({it.get('prob')*100:.1f}%)")
        except Exception:
            p.drawString(60,y, f"- {it}")
        y-=16
    p.drawString(40,y-10, 'Advice:'); p.drawString(60,y-30, row[3])
    p.showPage(); p.save(); buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'report_{hid}.pdf', mimetype='application/pdf')

@app.route('/api/hospitals', methods=['GET'])
@app.route('/api/hospitals', methods=['GET'])
def hospitals():
    import requests
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    location = request.args.get('location')
    try:
        if lat and lon:
            lat, lon = float(lat), float(lon)
        elif location:
            ge = requests.get(
                'https://nominatim.openstreetmap.org/search',
                params={'q': location, 'format':'json', 'limit':1},
                headers={'User-Agent': 'smarthealth-app/1.0'},
                timeout=10
            ).json()
            if not ge:
                return jsonify({'hospitals': []})
            lat, lon = float(ge[0]['lat']), float(ge[0]['lon'])
        else:
            return jsonify({'error':'Provide lat+lon or location param'}), 400

        query = f"""
        [out:json];
        node(around:5000,{lat},{lon})[amenity=hospital];
        out center;
        """
        r = requests.post('https://overpass-api.de/api/interpreter', data={'data': query}, timeout=15)
        data = r.json()
        results = []
        for el in data.get('elements', [])[:20]:
            results.append({
                'name': el.get('tags', {}).get('name', 'Unnamed'),
                'lat': el.get('lat'),
                'lon': el.get('lon')
            })
        return jsonify({'hospitals': results})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

