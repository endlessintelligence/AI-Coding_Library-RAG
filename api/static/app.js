// api/static/app.js - 前端核心逻辑（日期/时间段/座位地图/WebSocket/智能问答）

let TOKEN = localStorage.getItem('token') || '';
let USER = null;
let CURRENT_FLOOR = -1;
let SELECTED_DATE = null;
let SELECTED_SLOT = null;  // {start: Date, end: Date}
let SELECTED_SEAT = null;
let WS = null;

const DAY_NAMES = ['日','一','二','三','四','五','六'];
const TIME_SLOTS = [];
for (let h = 8; h < 22; h++) TIME_SLOTS.push({start:h, end:h+1, label:pad(h)+':00-'+pad(h+1)+':00'});
function pad(n) { return n<10?'0'+n:''+n; }

// ===== Auth =====
function showAuthTab(tab) {
  document.querySelectorAll('.auth-tabs .tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.auth-form').forEach(f=>f.classList.add('hidden'));
  if (tab==='login') {
    document.querySelector('.auth-tabs .tab:first-child').classList.add('active');
    document.getElementById('login-form').classList.remove('hidden');
  } else {
    document.querySelector('.auth-tabs .tab:last-child').classList.add('active');
    document.getElementById('register-form').classList.remove('hidden');
  }
}

document.getElementById('login-form').onsubmit = async (e) => {
  e.preventDefault();
  const r = await fetch('/api/login', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({student_id:document.getElementById('login-id').value,password:document.getElementById('login-pwd').value})
  });
  const d = await r.json();
  if (r.ok) {
    TOKEN = d.token; localStorage.setItem('token',TOKEN);
    document.getElementById('login-msg').textContent = '';
    await loadMain();
  } else {
    document.getElementById('login-msg').textContent = d.detail;
  }
};

document.getElementById('register-form').onsubmit = async (e) => {
  e.preventDefault();
  const r = await fetch('/api/register', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({student_id:document.getElementById('reg-id').value,password:document.getElementById('reg-pwd').value,name:document.getElementById('reg-name').value})
  });
  const d = await r.json();
  document.getElementById('reg-msg').textContent = r.ok ? '注册成功，请登录' : d.detail;
};

async function loadMain() {
  const r = await fetch('/api/me', {headers:{'Authorization':'Bearer '+TOKEN}});
  if (!r.ok) { logout(); return; }
  USER = await r.json();
  document.getElementById('user-display').textContent = USER.name + (USER.is_admin ? ' (管理员)' : '');
  document.getElementById('auth-page').classList.add('hidden');
  document.getElementById('main-page').classList.remove('hidden');
  if (USER.is_admin) document.getElementById('admin-panel').style.display = '';
  buildFloorTabs();
  loadDateTabs();
  loadMyReservations();
  if (USER.is_admin) { loadReleaseRecords(); loadAdminUsers(); }
  connectWebSocket();
}

function logout() {
  TOKEN = ''; localStorage.removeItem('token'); USER = null;
  if (WS) WS.close();
  document.getElementById('main-page').classList.add('hidden');
  document.getElementById('auth-page').classList.remove('hidden');
}

// ===== Floor Tabs =====
function buildFloorTabs() {
  const floors = [
    {key:-1,label:'负一楼 电脑区'},{key:2,label:'二楼 A-F'},{key:3,label:'三楼 G-L'},
    {key:4,label:'四楼 M-R'},{key:5,label:'五楼 S-Z'}
  ];
  const container = document.getElementById('floor-tabs');
  container.innerHTML = '';
  floors.forEach(f => {
    const btn = document.createElement('button');
    btn.textContent = f.label;
    btn.dataset.floor = f.key;
    if (f.key===CURRENT_FLOOR) btn.classList.add('active');
    btn.onclick = () => {
      CURRENT_FLOOR = f.key;
      container.querySelectorAll('button').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      if (SELECTED_SLOT) loadAvailableSeats();
    };
    container.appendChild(btn);
  });
}

// ===== Date Tabs =====
function loadDateTabs() {
  const container = document.getElementById('date-tabs');
  container.innerHTML = '';
  const now = new Date();
  for (let i = 0; i < 7; i++) {
    const d = new Date(now);
    d.setDate(d.getDate() + i);
    const div = document.createElement('div');
    div.className = 'date-tab' + (i===0?' active':'');
    div.innerHTML = '<div class="dow">周'+DAY_NAMES[d.getDay()]+'</div><div class="dom">'+pad(d.getMonth()+1)+'/'+pad(d.getDate())+'</div>';
    div.dataset.date = d.toISOString().slice(0,10);
    div.onclick = () => selectDate(div, d);
    container.appendChild(div);
  }
  SELECTED_DATE = new Date();
  loadTimeSlots();
}

function selectDate(el, d) {
  document.querySelectorAll('.date-tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  SELECTED_DATE = d;
  SELECTED_SLOT = null;
  SELECTED_SEAT = null;
  document.getElementById('selected-info').textContent = '请选择时间段';
  document.getElementById('btn-reserve').disabled = true;
  loadTimeSlots();
  document.getElementById('seat-grid').innerHTML = '<p class="hint" style="text-align:center;color:#adb5bd;grid-column:1/4">请在右侧选择时间段</p>';
}

// ===== Time Slots =====
function loadTimeSlots() {
  const container = document.getElementById('time-grid');
  container.innerHTML = '';
  const now = new Date();
  const isToday = SELECTED_DATE.toDateString() === now.toDateString();
  TIME_SLOTS.forEach(slot => {
    const div = document.createElement('div');
    div.className = 'time-slot';
    div.textContent = slot.label;
    div.dataset.slot = slot.start+'-'+slot.end;
    const slotTime = new Date(SELECTED_DATE);
    slotTime.setHours(slot.start, 0, 0, 0);
    if (isToday && slotTime <= now) {
      div.classList.add('past');
    } else {
      div.onclick = () => selectTimeSlot(div, slot);
    }
    container.appendChild(div);
  });
}

function selectTimeSlot(el, slot) {
  document.querySelectorAll('.time-slot').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  const st = new Date(SELECTED_DATE); st.setHours(slot.start,0,0,0);
  const et = new Date(SELECTED_DATE); et.setHours(slot.end,0,0,0);
  SELECTED_SLOT = {start:st, end:et};
  SELECTED_SEAT = null;
  document.getElementById('selected-info').textContent = slot.label;
  document.getElementById('btn-reserve').disabled = true;
  loadAvailableSeats();
}

// ===== Available Seats =====
async function loadAvailableSeats() {
  if (!SELECTED_SLOT) return;
  const grid = document.getElementById('seat-grid');
  grid.innerHTML = '<p class="hint" style="text-align:center;color:#adb5bd;grid-column:1/4">加载中...</p>';
  const st = localISO(SELECTED_SLOT.start);
  const et = localISO(SELECTED_SLOT.end);
  const r = await fetch('/api/seats/available?floor='+CURRENT_FLOOR+'&start_time='+st+'&end_time='+et, {headers:{'Authorization':'Bearer '+TOKEN}});
  if (!r.ok) { grid.innerHTML = '<p class="hint" style="text-align:center;color:#adb5bd;grid-column:1/4">加载失败</p>'; return; }
  const seats = await r.json();
  if (seats.length === 0) { grid.innerHTML = '<p class="hint" style="text-align:center;color:#adb5bd;grid-column:1/4">该楼层无座位</p>'; return; }
  grid.innerHTML = '';
  seats.forEach(s => {
    const div = document.createElement('div');
    div.className = 'seat-item ' + (s.available ? 'free' : 'occupied');
    div.dataset.seatId = s.id;
    let tags = '';
    if (s.category_letter) tags += '<span class="cat">'+s.category_letter+'</span>';
    if (s.has_computer) tags += '<span class="cat" style="background:#e7f5ff;color:#1a73e8">电脑</span>';
    div.innerHTML = '<span class="num">'+s.seat_number.split('-').pop()+'</span>' + tags;
    if (s.available) {
      div.onclick = () => selectSeat(div, s);
    }
    grid.appendChild(div);
  });
}

function selectSeat(el, seat) {
  document.querySelectorAll('.seat-item').forEach(s=>s.classList.remove('selected'));
  el.classList.add('selected');
  SELECTED_SEAT = seat;
  document.getElementById('selected-info').textContent = SELECTED_SLOT.start.getHours()+':00-'+SELECTED_SLOT.end.getHours()+':00 | '+(seat.has_computer?'🖥 ':'')+seat.seat_number;
  document.getElementById('btn-reserve').disabled = false;
  document.getElementById('reserve-msg').textContent = '';
}

// ===== Reservation =====
async function reserveSeat() {
  if (!SELECTED_SEAT || !SELECTED_SLOT) return;
  const body = {seat_id:SELECTED_SEAT.id, start_time:localISO(SELECTED_SLOT.start), end_time:localISO(SELECTED_SLOT.end)};
  const r = await fetch('/api/reservations', {
    method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},
    body:JSON.stringify(body)
  });
  const d = await r.json();
  document.getElementById('reserve-msg').textContent = r.ok ? '预约成功！' : d.detail;
  if (r.ok) {
    SELECTED_SEAT = null; SELECTED_SLOT = null;
    document.getElementById('btn-reserve').disabled = true;
    document.querySelectorAll('.time-slot').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.seat-item').forEach(s=>s.classList.remove('selected'));
    document.getElementById('selected-info').textContent = '请选择日期和时间段';
    loadMyReservations();
    loadAvailableSeats();
    setTimeout(() => document.getElementById('reserve-msg').textContent = '', 3000);
  }
}

async function loadMyReservations() {
  const r = await fetch('/api/reservations/my', {headers:{'Authorization':'Bearer '+TOKEN}});
  if (!r.ok) return;
  const list = await r.json();
  const container = document.getElementById('reservation-list');
  if (list.length === 0) { container.innerHTML = '<p class="hint">暂无预约</p>'; return; }
  container.innerHTML = '';
  list.forEach(res => {
    const div = document.createElement('div');
    div.className = 'res-card' + (res.status==='pending'||res.status==='checked_in'||res.status==='temp_leave'?' clickable':'');
    const floorLabel = res.floor===-1?'负一楼':res.floor+'楼';
    const st = res.start_time.slice(5,16).replace('T',' ');
    const et = res.end_time.slice(11,16);
    div.innerHTML = '<strong>'+floorLabel+' · '+(res.seat_number||'#'+res.seat_id)+'</strong> '+st+'~'+et+
      '<br><span class="status-tag '+res.status+'">'+statusLabel(res.status)+'</span>'+
      '<div class="actions">'+actionButtons(res)+'</div>';
    if (res.status==='pending'||res.status==='checked_in'||res.status==='temp_leave') {
      div.onclick = (e) => { if (e.target.tagName!=='BUTTON') jumpToReservation(res); };
    }
    container.appendChild(div);
  });
}

function jumpToReservation(res) {
  CURRENT_FLOOR = res.floor;
  document.getElementById('floor-tabs').querySelectorAll('button').forEach(b => b.classList.toggle('active', parseInt(b.dataset.floor)===res.floor));
  // Switch to the correct date and time slot
  const d = new Date(res.start_time);
  SELECTED_DATE = d;
  const dtabs = document.getElementById('date-tabs');
  dtabs.querySelectorAll('.date-tab').forEach(t => {
    const active = t.dataset.date === d.toISOString().slice(0,10);
    t.classList.toggle('active', active);
  });
  // Set the time slot
  const sh = d.getHours();
  const eh = new Date(res.end_time).getHours();
  const slot = TIME_SLOTS.find(s => s.start===sh && s.end===eh);
  if (slot) {
    SELECTED_SLOT = {start:d, end:new Date(res.end_time)};
    const fl = res.floor===-1?'负一楼':res.floor+'楼';
    document.getElementById('selected-info').textContent = slot.label+' | '+fl+' · '+(res.seat_number||'#'+res.seat_id);
    document.getElementById('btn-reserve').disabled = true;
    document.querySelectorAll('.time-slot').forEach(t=>t.classList.toggle('active', t.dataset.slot===sh+'-'+eh));
    loadAvailableSeats();
  }
}

function statusLabel(s) {
  const m = {pending:'待签到',checked_in:'已签到',temp_leave:'暂离中',completed:'已完成',cancelled:'已取消',auto_released:'已释放'};
  return m[s]||s;
}

function actionButtons(res) {
  let btns = '';
  if (res.status==='pending') {
    btns += '<button onclick="doAction('+res.id+',\'checkin\')">签到</button>';
    if (new Date(res.start_time) > new Date()) btns += '<button class="btn-cancel" onclick="doAction('+res.id+',\'cancel\')">取消</button>';
  }
  if (res.status==='checked_in') {
    btns += '<button onclick="doAction('+res.id+',\'temp-leave\')">暂离</button>';
    btns += '<button onclick="doAction('+res.id+',\'checkout\')">签退</button>';
  }
  if (res.status==='temp_leave') btns += '<button onclick="doAction('+res.id+',\'temp-return\')">返回</button>';
  if (['completed','cancelled','auto_released'].includes(res.status)) {
    btns += '<button class="btn-delete" onclick="deleteReservation('+res.id+')">删除</button>';
  }
  return btns;
}

async function deleteReservation(resId) {
  if (!confirm('确认删除此预约记录？')) return;
  const r = await fetch('/api/reservations/'+resId, {method:'DELETE', headers:{'Authorization':'Bearer '+TOKEN}});
  const d = await r.json();
  alert(d.message || d.detail);
  loadMyReservations();
}

async function doAction(resId, action) {
  const r = await fetch('/api/reservations/'+resId+'/'+action, {
    method:'POST', headers:{'Authorization':'Bearer '+TOKEN}
  });
  const d = await r.json();
  if (r.ok) {
    if (action==='checkout' || action==='cancel') {
      SELECTED_SLOT = null; SELECTED_SEAT = null;
      document.querySelectorAll('.time-slot').forEach(t=>t.classList.remove('active'));
      document.querySelectorAll('.seat-item').forEach(s=>s.classList.remove('selected'));
      document.getElementById('btn-reserve').disabled = true;
      document.getElementById('selected-info').textContent = '请选择日期和时间段';
    }
    if (action==='cancel') { alert(d.message); loadMyReservations(); if (SELECTED_SLOT) loadAvailableSeats(); return; }
  }
  alert(d.message || d.detail);
  loadMyReservations();
  if (SELECTED_SLOT) loadAvailableSeats();
}

// ===== Admin =====
async function adminRelease() {
  const seatNum = document.getElementById('release-seat').value.trim();
  const reason = document.getElementById('release-reason').value.trim();
  if (!seatNum || !reason) { alert('请填写座位号和释放原因'); return; }
  const fd = new FormData();
  fd.append('seat_number', seatNum);
  fd.append('reason', reason);
  const fileInput = document.getElementById('release-evidence');
  if (fileInput.files[0]) fd.append('evidence', fileInput.files[0]);
  const r = await fetch('/api/admin/release-by-seat', {method:'POST', headers:{'Authorization':'Bearer '+TOKEN}, body:fd});
  const d = await r.json();
  alert(d.message || d.detail);
  if (r.ok) {
    document.getElementById('release-seat').value = '';
    document.getElementById('release-reason').value = '';
    document.getElementById('release-evidence').value = '';
    loadReleaseRecords();
  }
}

async function loadReleaseRecords() {
  const r = await fetch('/api/admin/release-records', {headers:{'Authorization':'Bearer '+TOKEN}});
  if (!r.ok) return;
  const records = await r.json();
  const list = document.getElementById('release-list');
  if (records.length===0) { list.innerHTML = '<p class="hint">暂无释放记录</p>'; return; }
  list.innerHTML = records.map(r => '<div class="release-item"><b>'+(r.seat_number||'#'+r.seat_id)+'</b> '+r.reason+(r.evidence_image?' <span style="color:#1a73e8">[有证据]</span>':'')+' <span class="time">'+r.created_at.slice(5,16)+'</span></div>').join('');
}

// ===== Admin User Management =====
async function loadAdminUsers() {
  const r = await fetch('/api/admin/users', {headers:{'Authorization':'Bearer '+TOKEN}});
  if (!r.ok) return;
  const users = await r.json();
  const el = document.getElementById('user-list');
  if (users.length===0) { el.innerHTML = '<p class="hint">暂无用户</p>'; return; }
  el.innerHTML = users.map(u => '<div class="user-item"><span class="user-id">'+u.student_id+'</span>'+
    (u.is_admin?' <span class="admin-badge">管理员</span>':'')+
    (u.penalty_active?' <span class="penalty-badge">已暂停</span>':'')+
    (!u.is_admin?' <button class="btn-small '+(u.penalty_active?'btn-unsuspend':'btn-suspend')+'" onclick="togglePenalty('+u.id+')">'+(u.penalty_active?'解封':'暂停')+'</button>':'')+
    '</div>').join('');
}

async function togglePenalty(userId) {
  const r = await fetch('/api/admin/users/'+userId+'/toggle-penalty', {method:'POST', headers:{'Authorization':'Bearer '+TOKEN}});
  const d = await r.json();
  alert(d.message || d.detail);
  loadAdminUsers();
}

// ===== WebSocket =====
function connectWebSocket() {
  const proto = location.protocol==='https:'?'wss:':'ws:';
  WS = new WebSocket(proto+'//'+location.host+'/ws');
  WS.onopen = () => { const el = document.getElementById('ws-status'); el.className = 'ws-online'; el.textContent = 'online'; };
  WS.onclose = () => {
    const el = document.getElementById('ws-status'); el.className = 'ws-offline'; el.textContent = 'offline';
    setTimeout(connectWebSocket, 3000);
  };
  WS.onmessage = (e) => {
    try { const msg = JSON.parse(e.data); if (msg.type==='seat_update' && SELECTED_SLOT) loadAvailableSeats(); } catch(_) {}
  };
}

// ===== Chat =====
function toggleChat() {
  document.getElementById('chat-panel').classList.toggle('hidden');
  document.getElementById('chat-input').focus();
}

function toggleMaximize() {
  document.getElementById('chat-panel').classList.toggle('maximized');
  document.getElementById('btn-maximize').textContent =
    document.getElementById('chat-panel').classList.contains('maximized') ? '─' : '□';
}

function localISO(d) {
  const pad2 = n => n<10?'0'+n:''+n;
  return d.getFullYear()+'-'+pad2(d.getMonth()+1)+'-'+pad2(d.getDate())+'T'+pad2(d.getHours())+':'+pad2(d.getMinutes())+':'+pad2(d.getSeconds());
}
const AGENT_LABELS = {rules:'规则助手',resources:'资源助手',personnel:'人员管理助手',faq:'综合信息助手'};

async function sendChat() {
  const input = document.getElementById('chat-input');
  const q = input.value.trim();
  if (!q) return;
  input.value = '';
  const msgs = document.getElementById('chat-messages');
  document.querySelector('.chat-placeholder')?.remove();
  msgs.innerHTML += '<div class="chat-msg user">'+escapeHtml(q)+'</div>';

  // Show thinking indicator
  const thinking = document.getElementById('chat-thinking');
  const thinkingText = document.getElementById('thinking-text');
  thinking.classList.remove('hidden');
  thinkingText.textContent = '正在分析意图...';
  msgs.scrollTop = msgs.scrollHeight;

  try {
    const r = await fetch('/api/chat', {
      method:'POST', headers:{'Content-Type':'application/json','Authorization':'Bearer '+TOKEN},
      body:JSON.stringify({question:q})
    });
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '', answer = '';
    let routeShown = false;

    while (true) {
      const {done,value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream:true});
      const lines = buffer.split('\n');
      buffer = lines.pop()||'';
      for (const line of lines) {
        if (line.startsWith('event: ')) continue;
        if (line.startsWith('data: ')) {
          try {
            const d = JSON.parse(line.slice(6));
            if (d.decision && !routeShown) {
              routeShown = true;
              const label = AGENT_LABELS[d.decision.toLowerCase()] || d.decision;
              msgs.innerHTML += '<div class="chat-msg assistant"><div class="route-tag">路由至 '+label+'</div><small style="color:#adb5bd">'+d.reason+'</small></div>';
              thinkingText.textContent = label+' 正在处理...';
              msgs.scrollTop = msgs.scrollHeight;
            }
            if (d.agent) {
              const label = AGENT_LABELS[d.agent] || d.agent;
              thinkingText.textContent = label+' 生成回答中...';
              if (d.output) {
                // Intermediate result shown
              }
            }
            if (d.answer) answer = d.answer;
          } catch(_) {}
        }
      }
    }

    thinking.classList.add('hidden');
    if (answer) {
      msgs.innerHTML += '<div class="chat-msg assistant">'+escapeHtml(answer)+'</div>';
    }
  } catch(e) {
    thinking.classList.add('hidden');
    msgs.innerHTML += '<div class="chat-msg assistant" style="color:#e03131">请求失败: '+e.message+'</div>';
  }
  msgs.scrollTop = msgs.scrollHeight;
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

// ===== Init =====
if (TOKEN) loadMain();
