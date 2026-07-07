const chat = document.querySelector('#chat');
const form = document.querySelector('#chatForm');
const input = document.querySelector('#messageInput');
const sendBtn = document.querySelector('#sendBtn');
const resetBtn = document.querySelector('#resetBtn');
const errorBox = document.querySelector('#error');

let messages = [];
let busy = false;
let ended = false;

function scrollToBottom() { chat.scrollTo({ top: chat.scrollHeight, behavior: 'smooth' }); }
function timeNow() { return new Intl.DateTimeFormat('zh-CN', { hour:'2-digit', minute:'2-digit' }).format(new Date()); }
function addMessage(role, content) {
  const node = document.createElement('article');
  node.className = `message ${role}`;
  const avatar = document.createElement('div');
  avatar.className = 'avatar'; avatar.textContent = role === 'user' ? '你' : '心';
  const body = document.createElement('div');
  const bubble = document.createElement('div'); bubble.className = 'bubble'; bubble.textContent = content;
  const time = document.createElement('time'); time.textContent = timeNow();
  body.append(bubble, time); node.append(avatar, body); chat.append(node); scrollToBottom();
}
function addTyping() {
  const node = document.createElement('article');
  node.id = 'typing'; node.className = 'message assistant typing';
  node.innerHTML = '<div class="avatar">心</div><div class="bubble"><i></i><i></i><i></i></div>';
  chat.append(node); scrollToBottom();
}
function setBusy(value) { busy = value; sendBtn.disabled = value || ended; input.disabled = value || ended; }

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const content = input.value.trim();
  if (!content || busy || ended) return;
  errorBox.textContent = ''; messages.push({ role:'user', content }); addMessage('user', content);
  input.value = ''; input.style.height = 'auto'; setBusy(true); addTyping();
  try {
    const response = await fetch('/api/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ messages }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '请求失败');
    document.querySelector('#typing')?.remove();
    const reply = data.message || '谢谢你的分享。';
    messages.push({ role:'assistant', content:reply }); addMessage('assistant', reply);
    ended = Boolean(data.ended);
    if (ended) {
      const note = document.createElement('div'); note.className = 'ended'; note.textContent = '访谈结束'; chat.append(note); scrollToBottom();
    }
  } catch (error) {
    document.querySelector('#typing')?.remove(); messages.pop();
    errorBox.textContent = error.message || '网络连接异常，请稍后重试。'; input.value = content;
  } finally { setBusy(false); input.focus(); }
});

input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = `${Math.min(input.scrollHeight, 150)}px`; });
input.addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); } });
resetBtn.addEventListener('click', () => { window.location.reload(); });
