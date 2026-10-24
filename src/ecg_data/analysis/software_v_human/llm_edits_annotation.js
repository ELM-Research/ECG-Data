annotation = (() => {
  // Save from the original page so rendered controls never accumulate in the file.
  const template = document.documentElement.cloneNode(true);
  const categories = ['factual', 'preferential', 'uncertain'];
  const key = record => JSON.stringify([record.source, record.file, record.pair_index]);
  for (const record of data.pairs) record.annotation ??= {category: null, explanation: '', updated_at: null};
  let handle = null, saving = false, revision = 0, savedRevision = 0, error = '';

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
    <div class="annotation-actions"><button id="annotation-save">Enable HTML autosave</button></div>
    <p id="annotation-status" role="status" aria-live="polite"></p>
    <small id="annotation-help"></small>`;
  document.querySelector('.workspace').before(tools);
  const sample = data.annotation;
  $('annotation-sample').textContent = `${sample.sample_size} / ${sample.eligible_pairs} successfully classified pairs · Random sample without replacement · Seed ${sample.seed}. Overview and plots describe this sample.`;
  const canAutosave = typeof window.showSaveFilePicker === 'function';
  $('annotation-save').disabled = !canAutosave;
  $('annotation-help').textContent = canAutosave
    ? 'At the start of each editing session, select this HTML file to enable autosave. Every edit updates it. Reopen it to restore annotations. Return this same HTML file when finished.'
    : 'Open this file in desktop Chrome or Edge to enable annotation autosave.';

  function savedHtml() {
    const output = template.cloneNode(true);
    const snapshot = {...data, annotation_saved_at: new Date().toISOString()};
    output.querySelector('#data').textContent = JSON.stringify(snapshot).replace(/</g, '\\u003c');
    return '<!doctype html>\n' + output.outerHTML;
  }

  function updateStatus() {
    const count = data.pairs.filter(record => record.annotation.category !== null).length;
    $('annotation-progress').textContent = `${count} / ${data.pairs.length} labelled`;
    $('annotation-status').textContent = error || (!handle ? 'Enable HTML autosave to start annotating.'
      : saving ? `Saving to ${handle.name}…` : `Saved to ${handle.name}. Return this HTML file.`);
    $('annotation-status').className = error ? 'error' : 'muted';
    $('annotation-save').textContent = handle ? 'Save now' : 'Enable HTML autosave';
  }

  async function saveFile() {
    if (!handle || saving) return;
    saving = true;
    error = '';
    updateStatus();
    try {
      // A later edit waits for the current write, then replaces it with the latest state.
      while (savedRevision !== revision) {
        const current = revision;
        const contents = savedHtml();
        const stream = await handle.createWritable();
        try {
          await stream.write(contents);
          await stream.close();
        } catch (failure) {
          await stream.abort().catch(() => {});
          throw failure;
        }
        savedRevision = current;
      }
    } catch (failure) {
      error = `File save failed: ${failure.message}. Use Save now to retry before closing.`;
    } finally {
      saving = false;
      updateStatus();
    }
  }

  function changed() {
    selected.annotation.updated_at = new Date().toISOString();
    revision += 1;
    renderList();
    void saveFile();
  }

  function view(record) {
    const value = record.annotation;
    const disabled = handle ? '' : ' disabled';
    return `<section class="annotation-box" aria-label="Annotate Here"><h2>Annotate Here</h2>
      <fieldset${disabled}><legend>Your classification · choose one</legend><div class="annotation-options">${categories.map(category => `<label><input type="radio" name="annotation-category" value="${category}"${value.category === category ? ' checked' : ''}>${title(category)}</label>`).join('')}</div></fieldset>
      <label for="annotation-explanation">Brief explanation<textarea id="annotation-explanation" rows="3" placeholder="Why did you choose this category?"${disabled}>${escape(value.explanation)}</textarea></label>
      <div class="annotation-actions"><button id="annotation-clear"${disabled}>Clear annotation</button></div></section>`;
  }

  $('detail').addEventListener('change', event => {
    if (!handle || !selected || event.target.name !== 'annotation-category') return;
    selected.annotation.category = event.target.value;
    changed();
  });
  $('detail').addEventListener('input', event => {
    if (!handle || !selected || event.target.id !== 'annotation-explanation') return;
    selected.annotation.explanation = event.target.value;
    changed();
  });
  $('detail').addEventListener('click', event => {
    if (!handle || !selected || event.target.id !== 'annotation-clear') return;
    selected.annotation.category = null;
    selected.annotation.explanation = '';
    changed();
    renderDetail();
  });

  $('annotation-save').addEventListener('click', async () => {
    if (handle) { await saveFile(); return; }
    $('annotation-save').disabled = true;
    try {
      const filename = decodeURIComponent(window.location.pathname.split('/').pop()) || 'annotations.html';
      const chosen = await window.showSaveFilePicker({
        suggestedName: /\.html?$/i.test(filename) ? filename : 'annotations.html',
        types: [{description: 'Annotation HTML', accept: {'text/html': ['.html', '.htm']}}],
      });
      const file = await chosen.getFile();
      if (file.size) {
        const page = new DOMParser().parseFromString(await file.text(), 'text/html');
        const payload = page.getElementById('data');
        if (!payload) throw new Error('Choose an annotation HTML file.');
        const saved = JSON.parse(payload.textContent);
        if (saved.annotation?.sample_id !== sample.sample_id || saved.pairs?.length !== data.pairs.length
            || saved.pairs.some((record, index) => key(record) !== key(data.pairs[index]))) {
          throw new Error('This HTML file belongs to a different sample.');
        }
        for (const [index, record] of saved.pairs.entries()) {
          if (Date.parse(record.annotation?.updated_at || '') > (Date.parse(data.pairs[index].annotation.updated_at || '') || 0)) {
            data.pairs[index].annotation = record.annotation;
          }
        }
      }
      handle = chosen;
      revision += 1;
      await saveFile();
      renderList();
      renderDetail();
    } catch (failure) {
      if (failure.name !== 'AbortError') error = `Cannot use this file: ${failure.message}`;
    } finally {
      $('annotation-save').disabled = false;
      updateStatus();
    }
  });
  window.addEventListener('beforeunload', event => {
    if (savedRevision !== revision) {
      event.preventDefault();
      event.returnValue = '';
    }
  });

  updateStatus();
  return {view, label: record => `<small>${record.annotation.category ? `Annotated · ${title(record.annotation.category)}` : 'Unannotated'}</small>`};
})();
