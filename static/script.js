// static/script.js
const API = '/api';

// helper: show spinner in element
function setLoading(elem, on=true){
  if(on) elem.innerHTML = '<div class="spinner"></div>';
  else elem.innerHTML = '';
}

// Render predictions
function renderPredictions(data, container){
  if(data.error){
    container.innerHTML = `<div class="result"><strong>Error:</strong> ${data.error}</div>`;
    return;
  }
  const preds = data.predictions || [];
  let html = '<h3>🩺 Possible Conditions</h3>';
  html += '<ul class="pred-list">';
  preds.forEach(p => {
    const pct = Math.round((p.prob || 0) * 100);
    html += `<li class="pred-item"><span class="label">${p.label}</span><span class="prob">${pct}%</span></li>`;
  });
  html += '</ul>';
  html += `<p class="advice">💡 ${data.advice || ''}</p>`;
  container.innerHTML = html;
}

// Predict
async function predict(){
  const symptoms = document.getElementById('symptoms').value.trim();
  const out = document.getElementById('result');
  if(!symptoms){ alert('Please enter symptoms'); return; }
  try{
    setLoading(out, true);
    const res = await fetch(`${API}/predict`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ symptoms })
    });
    const data = await res.json();
    renderPredictions(data, out);
  } catch(err){
    out.innerHTML = `<div class="result"><strong>Error:</strong> Could not connect to backend.</div>`;
    console.error(err);
  }
}

// Chat
async function chat(){
  const q = document.getElementById('chat_input').value.trim();
  const out = document.getElementById('chat_out');
  if(!q){ alert('Enter a message'); return; }
  try{
    setLoading(out, true);
    const res = await fetch(`${API}/chat`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ message: q })
    });
    const data = await res.json();
    if(data.answer) out.innerHTML = `<div class="bubble bot">${data.answer}</div>`;
    else out.innerHTML = `<div class="bubble bot">No answer</div>`;
  }catch(err){
    out.innerHTML = `<div class="bubble bot">Error contacting server</div>`;
    console.error(err);
  }
}

// Voice recognition
function startRecognition(){
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if(!SpeechRecognition) return alert('SpeechRecognition not supported.');
  const recog = new SpeechRecognition(); recog.lang = 'en-US';
  recog.onresult = (e) => {
    const text = e.results[0][0].transcript;
    document.getElementById('symptoms').value = text;
  };
  recog.start();
}

// Find hospitals
async function findHosp(){
  const loc = document.getElementById('loc').value.trim();
  const out = document.getElementById('hosp_out');
  if(!loc){ alert('Enter a location'); return; }
  try{
    setLoading(out, true);
    const res = await fetch(`${API}/hospitals?location=` + encodeURIComponent(loc));
    const data = await res.json();
    if(data.hospitals && data.hospitals.length){
      let html = '<ul>';
      data.hospitals.forEach(h => {
        html += `<li>${h.name} <small>(${h.lat?.toFixed?.(3)}, ${h.lon?.toFixed?.(3)})</small></li>`;
      });
      html += '</ul>';
      out.innerHTML = html;
    } else out.innerHTML = '<div>No hospitals found.</div>';
  }catch(err){
    out.innerHTML = `<div>Error fetching hospitals.</div>`;
    console.error(err);
  }
}

// History
async function getHistory(){
  const out = document.getElementById('history');
  try{
    setLoading(out, true);
    const res = await fetch(`${API}/history`);
    const data = await res.json();
    if(Array.isArray(data) && data.length){
      let html = '';
      data.forEach(r => {
        const preds = Array.isArray(r.prediction) ? r.prediction.map(p=> `${p.label} (${Math.round((p.prob||0)*100)}%)`).join(', ') : JSON.stringify(r.prediction);
        html += `<div class="history-item">
                    <div><strong>${r.symptoms}</strong> <small style="color:var(--muted)"> — ${r.created_at}</small></div>
                    <div style="margin-top:6px">${preds}</div>
                    <div style="margin-top:8px"><a href="/api/report/${r.id}" target="_blank">Download PDF report</a></div>
                 </div>`;
      });
      out.innerHTML = html;
    } else out.innerHTML = '<div>No history yet.</div>';
  }catch(err){
    out.innerHTML = `<div>Error loading history</div>`;
    console.error(err);
  }
}

// hook up buttons after DOM loads
window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('predictBtn').addEventListener('click', predict);
  document.getElementById('chatBtn').addEventListener('click', chat);
  document.getElementById('voiceBtn').addEventListener('click', startRecognition);
  document.getElementById('findBtn').addEventListener('click', findHosp);
  document.getElementById('loadHistBtn').addEventListener('click', getHistory);
});
