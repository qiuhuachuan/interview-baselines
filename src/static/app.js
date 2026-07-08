const chat = document.querySelector('#chat');
const form = document.querySelector('#chatForm');
const input = document.querySelector('#messageInput');
const sendBtn = document.querySelector('#sendBtn');
const resetBtn = document.querySelector('#resetBtn');
const errorBox = document.querySelector('#error');
const picker = document.querySelector('#interviewerPicker');

let messages = [];
let busy = false;
let ended = false;
let interviewer = null;
let magiState = null;

const interviewerProfiles = {
  general: {
    name: '访谈智能体 A',
    greeting: '你好，我是访谈智能体 A。这里没有评判，你可以按照自己舒服的节奏来交流。最近有什么事情让你感到困扰，或者想从哪里开始聊起？'
  },
  dsm: {
    name: '访谈智能体 B',
    greeting: '你好，我是访谈智能体 B。接下来我会通过一些问题了解你的情况，你可以按照自己舒服的节奏回答。最近最想聊聊什么？'
  },
  mini: {
    name: '访谈智能体 C',
    greeting: '你好，我是访谈智能体 C。接下来我会通过一些问题了解你的情况，这些问题只用于初步了解，不代表正式诊断。你可以先说说，最近最困扰你的问题是什么？'
  },
  magi: {
    name: '访谈智能体 D',
    greeting: '你好，我是访谈智能体 D。接下来我会通过一些问题逐步了解你的情况，这些问题只用于初步了解，不代表正式诊断。最近最困扰你的问题是什么？'
  }
};

function scrollToBottom() {
  if (typeof chat.scrollTo === 'function') {
    chat.scrollTo({ top: chat.scrollHeight, behavior: 'smooth' });
  } else {
    chat.scrollTop = chat.scrollHeight;
  }
}
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
function setBusy(value) {
  busy = value;
  sendBtn.disabled = value || ended || !interviewer;
  input.disabled = value || ended || !interviewer;
}

function selectInterviewer(id) {
  const profile = interviewerProfiles[id];
  if (!profile || interviewer) return;
  interviewer = id;
  picker.hidden = true;
  chat.insertAdjacentHTML('afterbegin', '<div class="date-divider"><span>今天</span></div>');
  messages.push({ role: 'assistant', content: profile.greeting });
  addMessage('assistant', profile.greeting);
  document.querySelector('.brand-copy p').innerHTML = `<span class="status-dot"></span>${profile.name} · 访谈中`;
  resetBtn.hidden = false;
  input.placeholder = '说说此刻的感受…';
  setBusy(false);
  input.focus();
}

picker.addEventListener('click', (event) => {
  const button = event.target.closest('[data-interviewer]');
  if (button) selectInterviewer(button.getAttribute('data-interviewer'));
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const content = input.value.trim();
  if (!content || busy || ended) return;
  errorBox.textContent = ''; messages.push({ role:'user', content }); addMessage('user', content);
  input.value = ''; input.style.height = 'auto'; setBusy(true); addTyping();
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ interviewer, messages, magi_state: magiState })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '请求失败');
    if (interviewer === 'magi') magiState = data.state || magiState;
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
