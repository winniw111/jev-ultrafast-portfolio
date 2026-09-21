(() => {
  const rows = [...document.querySelectorAll('.trace-step')];
  const filters = [...document.querySelectorAll('.filter')];
  const replay = document.querySelector('#replay');
  if (!rows.length || !replay) return;

  let timer = null;
  const reset = () => {
    if (timer) clearInterval(timer);
    timer = null;
    replay.textContent = '▶ Replay';
    rows.forEach(row => row.classList.remove('pending', 'current', 'played'));
  };

  filters.forEach(button => button.addEventListener('click', () => {
    reset();
    filters.forEach(item => item.classList.toggle('active', item === button));
    rows.forEach(row => {
      row.hidden = button.dataset.filter !== 'ALL' && row.dataset.operation !== button.dataset.filter;
    });
  }));

  replay.addEventListener('click', () => {
    if (timer) {
      reset();
      return;
    }
    const visible = rows.filter(row => !row.hidden);
    let index = 0;
    rows.forEach(row => row.classList.remove('played', 'current'));
    visible.forEach(row => row.classList.add('pending'));
    replay.textContent = '■ Stop';

    const tick = () => {
      if (index > 0) visible[index - 1].classList.replace('current', 'played');
      if (index >= visible.length) {
        reset();
        return;
      }
      visible[index].classList.replace('pending', 'current');
      visible[index].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      index += 1;
    };
    tick();
    timer = setInterval(tick, 700);
  });
})();
