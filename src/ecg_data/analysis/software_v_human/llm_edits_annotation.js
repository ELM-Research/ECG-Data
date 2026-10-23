annotation = (() => {
  const categories = ['factual', 'preferential', 'uncertain'];
  const key = record => JSON.stringify([record.source, record.file, record.pair_index]);
  const blank = () => ({category: null, explanation: '', updated_at: null});
  const storageKey = `llm-edit-annotations:${data.annotation.sample_id}`;
  const values = Object.fromEntries(data.pairs.map(record => [key(record), blank()]));
  let handle = null, saving = false, revision = 0, savedRevision = -1, downloadedRevision = -1;
  let saveError = '', draftError = '', message = '';

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
  tools.setAttribute('aria-label', 'Annotation files');
  tools.innerHTML = `<div class="between"><h2>Annotations</h2><strong id="annotation-progress"></strong></div>
    <p id="annotation-sample" class="muted"></p>
    <div class="annotation-actions"><button id="annotation-save">Choose autosave file</button><button id="annotation-download">Download JSON</button><button id="annotation-load">Load annotations</button><input id="annotation-file" type="file" accept=".json,application/json" hidden></div>
    <p id="annotation-status" role="status" aria-live="polite"></p>
    <small id="annotation-help"></small>`;
  document.querySelector('.workspace').before(tools);
  const sample = data.annotation;
  $('annotation-sample').textContent = `${sample.sample_size} / ${sample.eligible_pairs} successfully classified pairs · Random sample without replacement · Seed ${sample.seed}. Overview and plots describe this sample.`;
  const canAutosave = typeof window.showSaveFilePicker === 'function';
  $('annotation-save').disabled = !canAutosave;
  $('annotation-help').textContent = canAutosave
    ? 'Choose a JSON file once; every edit then overwrites it. After reopening, choose the file again to resume autosave. Send the latest JSON file when finished.'
    : 'Automatic file saving needs Chrome or Edge. Browser drafts save on each edit; use Download JSON to save a file, and Load annotations to resume it elsewhere.';

  function readSaved(result) {
    if (result.schema_version !== 1 || result.sample_id !== sample.sample_id) throw new Error('This file belongs to a different sample or format.');
    if (!Array.isArray(result.pairs) || result.pairs.length !== data.pairs.length) throw new Error('The saved sample is incomplete.');
    const restored = {};
    for (const record of result.pairs) {
      const id = key(record), value = record.annotation;
      if (!Object.hasOwn(values, id) || Object.hasOwn(restored, id)) throw new Error('The saved pair identities do not match this sample.');
      if (!value || ![null, ...categories].includes(value.category) || typeof value.explanation !== 'string'
          || !(value.updated_at === null || typeof value.updated_at === 'string' && Number.isFinite(Date.parse(value.updated_at)))) {
        throw new Error('Invalid saved annotation.');
      }
      if (value.updated_at === null && (value.category !== null || value.explanation !== '')) throw new Error('Annotation timestamp is missing.');
      restored[id] = {category: value.category, explanation: value.explanation, updated_at: value.updated_at};
    }
    return restored;
  }

  function result(full = true) {
    const pairs = data.pairs.map(record => ({
      ...(full ? record : {source: record.source, file: record.file, pair_index: record.pair_index}),
      annotation: values[key(record)],
    }));
    const saved = {schema_version: 1, sample_id: sample.sample_id, pairs};
    return full ? {...saved, saved_at: new Date().toISOString(), exported_at: data.exported_at,
      run: data.run, sampling: sample, incomplete_tail: data.incomplete_tail} : saved;
  }

  function persistDraft() {
    try {
      localStorage.setItem(storageKey, JSON.stringify(result(false)));
      draftError = '';
    } catch (error) {
      draftError = `Browser draft unavailable: ${error.message}`;
    }
  }

  function updateStatus() {
    const count = Object.values(values).filter(value => value.category !== null).length;
    $('annotation-progress').textContent = `${count} / ${data.pairs.length} labelled`;
    let status = handle
      ? saving ? `Saving to ${handle.name}…` : savedRevision === revision ? `Saved to ${handle.name}.` : `Changes pending for ${handle.name}.`
      : 'Choose an autosave file, or download the latest JSON before sending it.';
    if (revision && !handle && !draftError) status = 'Browser draft saved. ' + status;
    $('annotation-status').textContent = [message, saveError || status, draftError].filter(Boolean).join(' ');
    $('annotation-status').className = saveError || draftError ? 'error' : 'muted';
    $('annotation-save').textContent = handle ? 'Save now' : 'Choose autosave file';
  }

  async function saveFile() {
    if (!handle || saving) return;
    saving = true;
    saveError = '';
    updateStatus();
    try {
      // Serialize writes; edits made during a write are saved by the next pass.
      while (savedRevision !== revision) {
        const current = revision;
        const contents = JSON.stringify(result(), null, 2) + '\n';
        const stream = await handle.createWritable();
        try {
          await stream.write(contents);
          await stream.close();
        } catch (error) {
          await stream.abort().catch(() => {});
          throw error;
        }
        savedRevision = current;
      }
    } catch (error) {
      saveError = `File save failed: ${error.message}. Use Save now to retry, or Download JSON.`;
    } finally {
      saving = false;
      updateStatus();
    }
  }

  function changed() {
    revision += 1;
    message = '';
    persistDraft();
    updateStatus();
    renderList();
    void saveFile();
  }

  function view(record) {
    const value = values[key(record)];
    return `<section class="annotation-box" aria-label="Annotate Here"><h2>Annotate Here</h2>
      <fieldset><legend>Your classification · choose one</legend><div class="annotation-options">${categories.map(category => `<label><input type="radio" name="annotation-category" value="${category}"${value.category === category ? ' checked' : ''}>${title(category)}</label>`).join('')}</div></fieldset>
      <label for="annotation-explanation">Brief explanation<textarea id="annotation-explanation" rows="3" placeholder="Why did you choose this category?">${escape(value.explanation)}</textarea></label>
      <div class="annotation-actions"><button id="annotation-clear">Clear annotation</button></div></section>`;
  }

  $('detail').addEventListener('change', event => {
    if (!selected || event.target.name !== 'annotation-category') return;
    const value = values[key(selected)];
    value.category = event.target.value;
    value.updated_at = new Date().toISOString();
    changed();
  });
  $('detail').addEventListener('input', event => {
    if (!selected || event.target.id !== 'annotation-explanation') return;
    const value = values[key(selected)];
    value.explanation = event.target.value;
    value.updated_at = new Date().toISOString();
    changed();
  });
  $('detail').addEventListener('click', event => {
    if (!selected || event.target.id !== 'annotation-clear') return;
    values[key(selected)] = {...blank(), updated_at: new Date().toISOString()};
    changed();
    renderDetail();
  });

  $('annotation-save').addEventListener('click', async () => {
    if (handle) { await saveFile(); return; }
    $('annotation-save').disabled = true;
    try {
      const chosen = await window.showSaveFilePicker({
        suggestedName: `annotations-${sample.sample_id.slice(0, 12)}.json`,
        types: [{description: 'Annotations JSON', accept: {'application/json': ['.json']}}],
      });
      const file = await chosen.getFile();
      if (file.size) {
        const restored = readSaved(JSON.parse(await file.text()));
        for (const [id, value] of Object.entries(restored)) {
          if (Date.parse(value.updated_at || '') > (Date.parse(values[id].updated_at || '') || 0)) values[id] = value;
        }
        revision += 1;
        persistDraft();
        renderList();
        renderDetail();
      }
      handle = chosen;
      message = '';
      await saveFile();
    } catch (error) {
      if (error.name !== 'AbortError') message = `Cannot use this file: ${error.message}`;
    } finally {
      $('annotation-save').disabled = false;
      updateStatus();
    }
  });

  $('annotation-download').addEventListener('click', () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(result(), null, 2) + '\n'], {type: 'application/json'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = `annotations-${sample.sample_id.slice(0, 12)}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    downloadedRevision = revision;
  });
  $('annotation-load').addEventListener('click', () => $('annotation-file').click());
  $('annotation-file').addEventListener('change', async event => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      const restored = readSaved(JSON.parse(await file.text()));
      Object.assign(values, restored);
      changed();
      renderDetail();
    } catch (error) {
      message = `Cannot load annotations: ${error.message}`;
      updateStatus();
    } finally {
      event.target.value = '';
    }
  });
  window.addEventListener('beforeunload', event => {
    if (revision && (handle ? savedRevision : downloadedRevision) !== revision) {
      event.preventDefault();
      event.returnValue = '';
    }
  });

  try {
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      Object.assign(values, readSaved(JSON.parse(saved)));
      revision += 1;
      message = 'Browser draft restored.';
    }
  } catch (error) {
    draftError = `Could not restore browser draft: ${error.message}`;
  }
  updateStatus();
  return {view, label: record => `<small>${values[key(record)].category ? `Annotated · ${title(values[key(record)].category)}` : 'Unannotated'}</small>`};
})();
