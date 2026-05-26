(function(){
  const DATA = JSON.parse(document.getElementById('dashboard-data').textContent);
  const $ = sel => document.querySelector(sel);
  const fmtUSD = v => v == null ? '—' : '$' + Math.round(v).toLocaleString('en-US');
  const fmtK = v => v == null ? '—' : '$' + Math.round(v/1000) + 'K';

  // --- Header / source card ---
  $('#crumb-date').textContent = DATA.meta.snapshot_date;
  $('#src-snapshot').textContent = DATA.meta.snapshot_iso;
  $('#src-postings').textContent = DATA.meta.total_jobs + ' · ' + DATA.meta.total_pool + ' total pool';
  $('#src-salary').textContent = DATA.meta.with_salary + ' / ' + DATA.meta.total_jobs;
  $('#footer-date').textContent = DATA.meta.snapshot_iso;
  $('#footer-run').textContent = 'run #' + DATA.meta.run_id;

  // --- Hero / KPIs ---
  $('#hero-count').textContent = DATA.meta.total_jobs;
  $('#kpi-jobs').textContent = DATA.meta.total_jobs;
  $('#kpi-jobs-sub').innerHTML = 'of ' + DATA.meta.total_pool + ' total in Greenhouse';
  $('#kpi-depts').textContent = DATA.depts.length;
  $('#kpi-depts-sub').textContent = 'active technical areas';
  $('#kpi-salary').textContent = DATA.meta.salary_median ? fmtK(DATA.meta.salary_median) : 'n/a';
  $('#kpi-salary-sub').innerHTML = 'avg ' + fmtK(DATA.meta.salary_avg) + ' · '
    + fmtK(DATA.meta.salary_min) + '–' + fmtK(DATA.meta.salary_max);
  $('#kpi-techs').textContent = DATA.meta.unique_techs;
  $('#kpi-techs-sub').textContent = DATA.meta.unique_techs + ' technologies detected';

  // --- Departments ---
  (function(){
    const total = DATA.depts.reduce((s,d)=>s+d.count,0);
    const max = Math.max(...DATA.depts.map(d=>d.count));
    $('#dept-list').innerHTML = DATA.depts.map((d,i) => {
      const focus = i === 0;
      const w = (d.count/max*100).toFixed(1);
      const pct = (d.count/total*100).toFixed(1);
      return `
        <div class="dept-row ${focus?'is-focus':''}">
          <div class="name">${d.name}<small>${d.subtitle || ''}</small></div>
          <div class="bar"><i style="width:${w}%"></i></div>
          <div class="count">${d.count}</div>
          <div class="share">${pct}%</div>
        </div>`;
    }).join('');
  })();

  // --- Seniority donut ---
  (function(){
    const total = DATA.seniority.reduce((s,x)=>s+x.count,0);
    $('#donut-total').textContent = total;
    const svg = $('#donut-svg');
    const cx=110, cy=110, r=86, sw=22;
    const C = 2*Math.PI*r;
    let acc = 0;
    let html = `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#ECE7DB" stroke-width="${sw}"/>`;
    DATA.seniority.forEach(s => {
      const frac = s.count/total;
      const dash = frac*C;
      const offset = -acc*C;
      html += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none"
                 stroke="${s.color}" stroke-width="${sw}"
                 stroke-dasharray="${dash} ${C-dash}"
                 stroke-dashoffset="${offset}"
                 stroke-linecap="butt"/>`;
      acc += frac;
    });
    svg.innerHTML = html;

    $('#legend').innerHTML = DATA.seniority.map(s => `
      <div class="item">
        <span class="sw" style="background:${s.color}"></span>
        <span>${s.label}</span>
        <span class="cnt">${s.count}</span>
        <span class="pct">${(s.count/total*100).toFixed(1)}%</span>
      </div>`).join('');
  })();

  // --- Tech / Skills per department (scrollable horizontal) ---
  function renderColumnar(targetId, source){
    document.getElementById(targetId).innerHTML = source.map(col => {
      const max = Math.max(...col.items.map(it=>it.count), 1);
      const rows = col.items.map((it,i) => `
        <div class="tech-row">
          <span class="rk">${String(i+1).padStart(2,'0')}</span>
          <span class="tn">${it.name}</span>
          <span class="tech-bar"><i style="width:${(it.count/max*100).toFixed(1)}%"></i></span>
          <span class="cnt">${it.count}</span>
        </div>`).join('');
      return `<div class="tech-col">
        <h3>${col.dept}</h3>
        <div class="sub">${col.subtitle}</div>
        ${rows || '<div class="sub" style="margin-top:10px">no data</div>'}
      </div>`;
    }).join('');
  }
  renderColumnar('tech-grid',   DATA.tech_by_dept);

  // --- ROI per tech ---
  (function(){
    if (!DATA.roi || !DATA.roi.length) {
      $('#roi-table').innerHTML = '<div class="empty-state">no postings with published salary to compute ROI</div>';
      return;
    }
    const max = Math.max(...DATA.roi.map(r=>r.avg_salary));
    $('#roi-table').innerHTML = DATA.roi.map((r,i) => `
      <div class="roi-row">
        <span class="rk">${String(i+1).padStart(2,'0')}</span>
        <span class="tn">${r.tech}</span>
        <span class="roi-bar"><i style="width:${(r.avg_salary/max*100).toFixed(1)}%"></i></span>
        <span class="sal">${fmtUSD(r.avg_salary)}</span>
        <span class="n">n=${r.n}</span>
      </div>`).join('');
  })();

  // --- Salary by department ---
  (function(){
    if (!DATA.salary_by_dept.length) {
      $('#salary-list').innerHTML = '<div class="empty-state">no salary data available</div>';
      return;
    }
    const allMin = Math.min(...DATA.salary_by_dept.map(s=>s.min));
    const allMax = Math.max(...DATA.salary_by_dept.map(s=>s.max));
    // Round scale to nearest 50k
    const SMIN = Math.floor(allMin/1000/50)*50;
    const SMAX = Math.ceil(allMax/1000/50)*50;
    const ticks = 6;
    const step = (SMAX - SMIN) / (ticks-1);
    $('#salary-scale').innerHTML = Array.from({length:ticks}, (_,i) =>
      `<span>$${Math.round(SMIN + step*i)}K</span>`).join('');

    const pos = v => ((v/1000 - SMIN) / (SMAX - SMIN)) * 100;
    $('#salary-list').innerHTML = DATA.salary_by_dept.map(s => `
      <div class="salary-row">
        <div class="lbl"><strong>${s.dept}</strong><small>n=${s.count} · avg ${fmtK(s.avg)}</small></div>
        <div class="track">
          <span class="axis"></span>
          <span class="range" style="left:${pos(s.min)}%;width:${pos(s.max)-pos(s.min)}%"></span>
          <span class="median" style="left:${pos(s.median)}%"></span>
        </div>
        <div class="stat">${fmtK(s.min)} – ${fmtK(s.max)}<br/><b>median ${fmtK(s.median)}</b></div>
      </div>`).join('');
  })();

  // --- Filters + search + paginated jobs table ---
  const state = {
    dept: 'ALL',
    seniorityFilter: null,
    remoteOnly: false,
    query: '',
    page: 1,
    pageSize: 25,
  };

  function buildChips(){
    const counts = {};
    DATA.jobs.forEach(j => { counts[j.dept] = (counts[j.dept]||0) + 1; });
    const remoteCount = DATA.jobs.filter(j => j.is_remote).length;
    const seniorPlus = DATA.jobs.filter(j => ['Senior','Staff','Principal','Lead','Manager','Director'].includes(j.seniority)).length;

    const chips = [
      {key:'ALL', label:`All · ${DATA.jobs.length}`},
      ...DATA.depts.map(d => ({key:'dept:'+d.name, label:`${d.short} · ${d.count}`})),
      {key:'remote', label:`Remote · ${remoteCount}`},
      {key:'senior+', label:`Senior+ · ${seniorPlus}`},
    ];

    const html = chips.map(c => `<button class="chip" data-key="${c.key}">${c.label}</button>`).join('');
    const search = $('#search-input');
    search.insertAdjacentHTML('beforebegin', html);

    document.querySelectorAll('.chip').forEach(c => {
      c.addEventListener('click', () => {
        const key = c.dataset.key;
        if (key === 'ALL') { state.dept='ALL'; state.remoteOnly=false; state.seniorityFilter=null; }
        else if (key === 'remote') { state.remoteOnly = !state.remoteOnly; }
        else if (key === 'senior+') { state.seniorityFilter = state.seniorityFilter ? null : 'senior+'; }
        else if (key.startsWith('dept:')) { state.dept = state.dept === key.slice(5) ? 'ALL' : key.slice(5); }
        state.page = 1;
        render();
      });
    });

    $('#search-input').addEventListener('input', e => {
      state.query = e.target.value.toLowerCase().trim();
      state.page = 1;
      render();
    });
    $('#prev-page').addEventListener('click', () => { if (state.page>1){state.page--;render();} });
    $('#next-page').addEventListener('click', () => { state.page++;render(); });
  }

  function filtered(){
    const seniorSet = new Set(['Senior','Staff','Principal','Lead','Manager','Director']);
    return DATA.jobs.filter(j => {
      if (state.dept !== 'ALL' && j.dept !== state.dept) return false;
      if (state.remoteOnly && !j.is_remote) return false;
      if (state.seniorityFilter === 'senior+' && !seniorSet.has(j.seniority)) return false;
      if (state.query) {
        const hay = (j.title + ' ' + j.stack.join(' ') + ' ' + j.location).toLowerCase();
        if (!hay.includes(state.query)) return false;
      }
      return true;
    });
  }

  function render(){
    document.querySelectorAll('.chip').forEach(c => {
      const k = c.dataset.key;
      let active = false;
      if (k === 'ALL') active = state.dept==='ALL' && !state.remoteOnly && !state.seniorityFilter;
      else if (k === 'remote') active = state.remoteOnly;
      else if (k === 'senior+') active = state.seniorityFilter === 'senior+';
      else if (k.startsWith('dept:')) active = state.dept === k.slice(5);
      c.classList.toggle('active', active);
    });

    const list = filtered();
    const total = list.length;
    const pages = Math.max(1, Math.ceil(total / state.pageSize));
    if (state.page > pages) state.page = pages;
    const start = (state.page-1) * state.pageSize;
    const page = list.slice(start, start + state.pageSize);

    $('#jobs-meta').textContent = `${total} filtered · page ${state.page}/${pages}`;
    $('#pager-info').textContent = total === 0
      ? 'no results'
      : `showing ${start+1}–${Math.min(start+state.pageSize, total)} of ${total}`;
    $('#prev-page').disabled = state.page <= 1;
    $('#next-page').disabled = state.page >= pages;

    if (!page.length) {
      $('#jobs-tbody').innerHTML = `<tr><td colspan="6" class="empty-state">no results for the current filters</td></tr>`;
      return;
    }

    $('#jobs-tbody').innerHTML = page.map(j => `
      <tr onclick="window.open('${j.url}', '_blank', 'noopener')">
        <td class="role"><a href="${j.url}" target="_blank" rel="noopener">${j.title}</a><small>${j.subtitle || ''}</small></td>
        <td><span class="tag dept">${j.dept_short}</span></td>
        <td><span class="sen-pill">${j.seniority}</span></td>
        <td>${j.stack.slice(0,5).map(t=>`<span class="tag">${t}</span>`).join('') || '<span class="tag" style="opacity:.5">—</span>'}</td>
        <td>${j.location}${j.is_remote ? ' <span class="tag" style="margin-left:4px">remote</span>' : ''}</td>
        <td class="num">${j.salary_label}</td>
      </tr>`).join('');
  }

  buildChips();
  render();
})();
