const form = document.querySelector('#pick-form');
const result = document.querySelector('#result');
const balls = document.querySelector('#balls');
const meta = document.querySelector('#result-meta');
const error = document.querySelector('#error');
const button = document.querySelector('#recommend-button');
const dateInput = document.querySelector('#draw-date');

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  error.hidden = true;
  result.hidden = true;
  button.disabled = true;
  button.innerHTML = '正在摇号 <span>···</span>';
  try {
    const response = await fetch('/api/recommend', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({date: dateInput.value})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || '暂时无法生成号码');
    balls.innerHTML = [
      ...data.front.map(n => `<span class="ball front">${String(n).padStart(2, '0')}</span>`),
      '<i></i>',
      ...data.back.map(n => `<span class="ball back">${String(n).padStart(2, '0')}</span>`)
    ].join('');
    meta.textContent = `${data.date} · 仅适用于本期开奖`;
    result.hidden = false;
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  } finally {
    button.disabled = false;
    button.innerHTML = '给我一注 <span>→</span>';
  }
});
