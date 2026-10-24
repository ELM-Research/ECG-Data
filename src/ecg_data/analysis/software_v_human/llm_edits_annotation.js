annotation = (() => {
  // Save from the original page so rendered controls never accumulate in the file.
  const template = document.documentElement.cloneNode(true);
  const categories = ['factual', 'preferential', 'uncertain'];
  const key = record => JSON.stringify([record.source, record.file, record.pair_index]);
  const sample = data.annotation;
  const storageKey = `llm-edit-annotations:${sample.sample_id}`;
  for (const record of data.pairs) record.annotation ??= {category: null, explanation: '', updated_at: null};
  let unsaved = false, error = '';

  const style = document.createElement('style');
  style.textContent = `
    .annotation-box { background: #edf4fa; border: 2px solid var(--blue); border-radius: 8px; padding: 18px; margin: 20px 0; }
    .annotation-box h2 { color: var(--blue); }
    .annotation-options, .annotation-actions { display: flex; flex-wrap: wrap; gap: 10px; margin: 12px 0; }
    .annotation-options label { display: flex; align-items: center; gap: 8px; padding: 9px 14px; background: white; border: 1px solid var(--line); border-radius: 7px; cursor: pointer; color: var(--ink); }
    .annotation-options label:has(:checked) { border-color: var(--blue); box-shadow: inset 0 0 0 1px var(--blue); }
    .annotation-options input { width: auto; accent-color: var(--blue); }
    .annotation-box fieldset { border: 0; padding: 0; margin: 0; }
    .annotation-box legend { font-size: 12px; color: var(--muted); }
    .annotation-box textarea { width: 100%; resize: vertical; min-height: 80px; padding: 10px; border: 1px solid var(--line); border-radius: 7px; font: inherit; color: var(--ink); }
    .annotation-box textarea:focus { outline: 2px solid var(--blue); outline-offset: 2px; }
  `;
  document.head.append(style);
  const tools = document.createElement('section');
  tools.className = 'panel';
  tools.setAttribute('aria-label', 'Annotation saving');
  tools.innerHTML = `<div class="between"><h2>Annotations</h2><strong id="annotation-progress"></strong></div>
    <p id="annotation-sample" class="muted"></p>
    <div class="annotation-actions"><button id="annotation-download">Download annotated HTML</button></div>
    <p id="annotation-status" role="status" aria-live="polite"></p>
    <small id="annotation-help"></small>`;
  document.querySelector('.workspace').before(tools);
  $('annotation-sample').textContent = `${sample.sample_size} / ${sample.eligible_pairs} eligible pairs · ${sample.method} · Seed ${sample.seed}. Overview and plots describe this sample.`;
  $('annotation-help').textContent = 'Every edit saves automatically in this browser. Reopen this same file in the same browser to continue. Download the annotated HTML to send your work or move it elsewhere. The original HTML file is not modified.';

  function savedHtml() {
    const output = template.cloneNode(true);
    const snapshot = {...data, annotation_saved_at: new Date().toISOString()};
    output.querySelector('#data').textContent = JSON.stringify(snapshot).replace(/</g, '\\u003c');
    return '<!doctype html>\n' + output.outerHTML;
  }

  function updateStatus() {
    const count = data.pairs.filter(record => record.annotation.category !== null).length;
    $('annotation-progress').textContent = `${count} / ${data.pairs.length} labelled`;
    $('annotation-status').textContent = error || 'Saved in this browser.';
    $('annotation-status').className = error ? 'error' : 'muted';
  }

  function save() {
    try {
      const pairs = data.pairs.map(({source, file, pair_index, annotation}) => ({source, file, pair_index, annotation}));
      localStorage.setItem(storageKey, JSON.stringify({sample_id: sample.sample_id, pairs}));
      unsaved = false;
      error = '';
    } catch (failure) {
      error = `Automatic saving failed: ${failure.message}. Download the annotated HTML before closing.`;
    }
    updateStatus();
  }

  function changed() {
    selected.annotation.updated_at = new Date().toISOString();
    unsaved = true;
    save();
    renderList();
  }

  function view(record) {
    const value = record.annotation;
    return `<section class="annotation-box" aria-label="Annotate Here"><h2>Annotate Here</h2>
      <fieldset><legend>Your classification · choose one</legend><div class="annotation-options">${categories.map(category => `<label><input type="radio" name="annotation-category" value="${category}"${value.category === category ? ' checked' : ''}>${title(category)}</label>`).join('')}</div></fieldset>
      <label for="annotation-explanation">Brief explanation<textarea id="annotation-explanation" rows="3" placeholder="Why did you choose this category?">${escape(value.explanation)}</textarea></label>
      <div class="annotation-actions"><button id="annotation-clear">Clear annotation</button></div></section>`;
  }

  $('detail').addEventListener('change', event => {
    if (!selected || event.target.name !== 'annotation-category') return;
    selected.annotation.category = event.target.value;
    changed();
  });
  $('detail').addEventListener('input', event => {
    if (!selected || event.target.id !== 'annotation-explanation') return;
    selected.annotation.explanation = event.target.value;
    changed();
  });
  $('detail').addEventListener('click', event => {
    if (!selected || event.target.id !== 'annotation-clear') return;
    selected.annotation.category = null;
    selected.annotation.explanation = '';
    changed();
    renderDetail();
  });

  $('annotation-download').addEventListener('click', () => {
    const url = URL.createObjectURL(new Blob([savedHtml()], {type: 'text/html'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = `annotations-${sample.sample_id.slice(0, 12)}.html`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    unsaved = false;
  });
  window.addEventListener('beforeunload', event => {
    if (unsaved) {
      event.preventDefault();
      event.returnValue = '';
    }
  });

  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
    if (saved) {
      if (saved.sample_id !== sample.sample_id || !Array.isArray(saved.pairs) || saved.pairs.length !== data.pairs.length
          || saved.pairs.some((record, index) => {
            const value = record.annotation;
            return key(record) !== key(data.pairs[index]) || !value || ![null, ...categories].includes(value.category)
              || typeof value.explanation !== 'string' || (value.updated_at === null
                ? value.category !== null || value.explanation !== ''
                : typeof value.updated_at !== 'string' || !Number.isFinite(Date.parse(value.updated_at)));
          })) {
        throw new Error('Invalid saved annotations for this sample.');
      }
      for (const [index, record] of saved.pairs.entries()) {
        if (Date.parse(record.annotation.updated_at) >= (Date.parse(data.pairs[index].annotation.updated_at) || 0)) {
          data.pairs[index].annotation = record.annotation;
        }
      }
    }
    save();
  } catch (failure) {
    error = `Cannot restore browser annotations: ${failure.message}. Download the annotated HTML before closing.`;
    updateStatus();
  }
  return {view, label: record => `<small>${record.annotation.category ? `Annotated · ${title(record.annotation.category)}` : 'Unannotated'}</small>`};
})();
