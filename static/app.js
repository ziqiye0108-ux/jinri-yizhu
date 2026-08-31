const form = document.querySelector('#pick-form');
const result = document.querySelector('#result');
const balls = document.querySelector('#balls');
const meta = document.querySelector('#result-meta');
const error = document.querySelector('#error');
const button = document.querySelector('#recommend-button');
const dateInput = document.querySelector('#draw-date');
const dateTrigger = document.querySelector('#date-picker-trigger');
const selectedText = document.querySelector('#selected-date-text');
const selectedWeekday = dateTrigger.querySelector('small');
const sheet = document.querySelector('#calendar-sheet');
const grid = document.querySelector('#calendar-grid');
const calendarTitle = document.querySelector('#calendar-title');
const weekdayNames = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
const validWeekdays = new Set([1, 3, 6]);
let visibleMonth = new Date(`${dateInput.value}T12:00:00`);

function localISO(value) {
  const y = value.getFullYear();
  const m = String(value.getMonth() + 1).padStart(2, '0');
  const d = String(value.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function renderCalendar() {
  const year = visibleMonth.getFullYear();
  const month = visibleMonth.getMonth();
  const firstDay = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  calendarTitle.textContent = `${year}年${month + 1}月`;
  grid.innerHTML = '';
  for (let i = 0; i < firstDay.getDay(); i += 1) grid.insertAdjacentHTML('beforeend', '<span></span>');
  for (let day = 1; day <= daysInMonth; day += 1) {
    const value = new Date(year, month, day);
    const iso = localISO(value);
    const enabled = value >= today && validWeekdays.has(value.getDay());
    const cell = document.createElement('button');
    cell.type = 'button';
    cell.textContent = day;
    cell.disabled = !enabled;
    cell.className = iso === dateInput.value ? 'selected' : '';
    if (enabled) cell.addEventListener('click', () => selectDate(value));
    grid.appendChild(cell);
  }
}

function selectDate(value) {
  const iso = localISO(value);
  dateInput.value = iso;
  dateInput.setAttribute('value', iso);
  selectedWeekday.textContent = weekdayNames[value.getDay()];
  selectedText.textContent = `${value.getMonth() + 1}月${value.getDate()}日`;
  closeCalendar();
}

function openCalendar() {
  visibleMonth = new Date(`${dateInput.value}T12:00:00`);
  renderCalendar();
  sheet.hidden = false;
  document.body.classList.add('sheet-open');
}

function closeCalendar() {
  sheet.hidden = true;
  document.body.classList.remove('sheet-open');
  dateTrigger.focus();
}

dateTrigger.addEventListener('click', openCalendar);
sheet.querySelector('.sheet-backdrop').addEventListener('click', closeCalendar);
document.querySelector('#prev-month').addEventListener('click', () => { visibleMonth.setDate(1); visibleMonth.setMonth(visibleMonth.getMonth() - 1); renderCalendar(); });
document.querySelector('#next-month').addEventListener('click', () => { visibleMonth.setDate(1); visibleMonth.setMonth(visibleMonth.getMonth() + 1); renderCalendar(); });

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
    meta.textContent = data.date;
    result.hidden = false;
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  } finally {
    button.disabled = false;
    button.innerHTML = '给我一注 <span>→</span>';
  }
});
