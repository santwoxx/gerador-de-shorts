// ==========================================================================
// AUTOSHORTS AI - CLIENT-SIDE LOGIC (v4.0 - Watermark & Preset Live Editor)
// ==========================================================================

const state = {
    currentVideo: null,
    currentClips: [],
    activeTaskId: null,
    pollInterval: null,
    isAnalyzing: false,
    isGenerating: false,
    isBatchMode: false,
    activeAbortController: null,
    settings: {
        provider: localStorage.getItem('autoshorts_provider') || 'auto',
        geminiKey: localStorage.getItem('autoshorts_gemini_key') || '',
        groqKey: localStorage.getItem('autoshorts_groq_key') || '',
        watermarkText: localStorage.getItem('autoshorts_wm_text') || '@meucanal',
        watermarkPos: localStorage.getItem('autoshorts_wm_pos') || 'top_right',
        watermarkType: localStorage.getItem('autoshorts_wm_type') || 'text',
        watermarkScale: parseInt(localStorage.getItem('autoshorts_wm_scale') || '250', 10),
        watermarkOpacity: parseFloat(localStorage.getItem('autoshorts_wm_opacity') || '0.9'),
        watermarkImageName: localStorage.getItem('autoshorts_wm_img') || '',
        watermarkPresetId: localStorage.getItem('autoshorts_wm_preset_id') || 'canal_top_right',
        subtitleStyle: localStorage.getItem('autoshorts_sub_style') || 'yellow_viral',
        layoutMode: localStorage.getItem('autoshorts_layout') || 'blur_bg',
        clipMode: localStorage.getItem('autoshorts_clip_mode') || 'viral_highlights',
        maxClips: parseInt(localStorage.getItem('autoshorts_max_clips') || '5', 10),
        clipDuration: parseInt(localStorage.getItem('autoshorts_clip_duration') || '60', 10),
    }
};

const watermarkState = {
    presets: [],
    images: [],
    current: {
        type: state.settings.watermarkType,
        text: state.settings.watermarkText,
        position: state.settings.watermarkPos,
        scale: state.settings.watermarkScale,
        opacity: state.settings.watermarkOpacity,
        image_name: state.settings.watermarkImageName
    }
};

const el = {
    ytUrlInput: document.getElementById('yt-url-input'),
    btnPaste: document.getElementById('btn-paste-url'),
    btnAnalyze: document.getElementById('btn-analyze'),
    analyzeSpinner: document.getElementById('analyze-spinner'),
    cfgWmPreset: document.getElementById('cfg-wm-preset'),
    btnOpenWmEditor: document.getElementById('btn-open-wm-editor'),
    cfgSubtitleStyle: document.getElementById('cfg-subtitle-style'),
    cfgLayoutMode: document.getElementById('cfg-layout-mode'),
    cfgClipMode: document.getElementById('cfg-clip-mode'),
    cfgMaxClips: document.getElementById('cfg-max-clips'),
    cfgClipDuration: document.getElementById('cfg-clip-duration'),
    cfgStartOffset: document.getElementById('cfg-start-offset'),
    sequentialInfoBanner: document.getElementById('sequential-info-banner'),
    seqInfoText: document.getElementById('seq-info-text'),
    btnSeqGenerateNow: document.getElementById('btn-seq-generate-now'),
    reactConfigPanel: document.getElementById('react-config-panel'),
    cfgReactCamPos: document.getElementById('cfg-react-cam-pos'),
    cfgReactCamOrder: document.getElementById('cfg-react-cam-order'),
    cfgReactRatio: document.getElementById('cfg-react-ratio'),
    reactAlertBanner: document.getElementById('react-alert-banner'),
    reactAlertTitle: document.getElementById('react-alert-title'),
    reactAlertText: document.getElementById('react-alert-text'),
    metaGenreBadge: document.getElementById('meta-genre-badge'),
    resultsSection: document.getElementById('results-section'),
    metaThumb: document.getElementById('meta-thumb'),
    metaTitle: document.getElementById('meta-title'),
    metaChannel: document.getElementById('meta-channel'),
    metaDuration: document.getElementById('meta-duration'),
    metaClipsCount: document.getElementById('meta-clips-count'),
    metaTranscriptCount: document.getElementById('meta-transcript-count'),
    metaEngineUsed: document.getElementById('meta-engine-used'),
    clipsGrid: document.getElementById('clips-grid'),
    btnGenerateAll: document.getElementById('btn-generate-all'),
    progressModal: document.getElementById('progress-modal'),
    progressBarFill: document.getElementById('progress-bar-fill'),
    progressPercentage: document.getElementById('progress-percentage'),
    progressStatusText: document.getElementById('progress-status-text'),
    progressStageStep: document.getElementById('progress-stage-step'),
    stepSubs: document.getElementById('step-subs'),
    stepDownload: document.getElementById('step-download'),
    stepRender: document.getElementById('step-render'),
    stepFinish: document.getElementById('step-finish'),
    batchProgressInfo: document.getElementById('batch-progress-info'),
    batchCounterText: document.getElementById('batch-counter-text'),
    batchMiniBarFill: document.getElementById('batch-mini-bar-fill'),
    previewModal: document.getElementById('preview-modal'),
    previewVideo: document.getElementById('preview-video-element'),
    previewTitle: document.getElementById('preview-clip-title'),
    previewMeta: document.getElementById('preview-clip-meta'),
    btnDownloadShort: document.getElementById('btn-download-short'),
    btnCopyTitle: document.getElementById('btn-copy-title'),
    btnClosePreview: document.getElementById('btn-close-preview'),
    settingsModal: document.getElementById('settings-modal'),
    btnOpenSettings: document.getElementById('btn-open-settings'),
    btnCloseSettings: document.getElementById('btn-close-settings'),
    btnSaveSettings: document.getElementById('btn-save-settings'),
    settingProvider: document.getElementById('setting-provider'),
    settingGeminiKey: document.getElementById('setting-gemini-key'),
    settingGroqKey: document.getElementById('setting-groq-key'),
    statDownloadsMb: document.getElementById('stat-downloads-mb'),
    statOutputsMb: document.getElementById('stat-outputs-mb'),
    btnClearCache: document.getElementById('btn-clear-cache'),
    btnViewLibrary: document.getElementById('btn-view-library'),
    librarySection: document.getElementById('library-section'),
    libraryGrid: document.getElementById('library-grid'),
    btnRefreshLibrary: document.getElementById('btn-refresh-library'),
    toastContainer: document.getElementById('toast-container'),
    // Watermark Editor Modal Elements
    wmEditorModal: document.getElementById('wm-editor-modal'),
    btnCloseWmEditor: document.getElementById('btn-close-wm-editor'),
    wmTypeSelect: document.getElementById('wm-type-select'),
    wmTextGroup: document.getElementById('wm-text-group'),
    wmTextInput: document.getElementById('wm-text-input'),
    wmImageGroup: document.getElementById('wm-image-group'),
    wmImageSelect: document.getElementById('wm-image-select'),
    btnUploadWmFile: document.getElementById('btn-upload-wm-file'),
    wmFileInput: document.getElementById('wm-file-input'),
    wmPosSelect: document.getElementById('wm-pos-select'),
    wmScaleGroup: document.getElementById('wm-scale-group'),
    wmScaleRange: document.getElementById('wm-scale-range'),
    wmScaleVal: document.getElementById('wm-scale-val'),
    wmOpacityRange: document.getElementById('wm-opacity-range'),
    wmOpacityVal: document.getElementById('wm-opacity-val'),
    wmPresetNameInput: document.getElementById('wm-preset-name-input'),
    btnSaveWmPreset: document.getElementById('btn-save-wm-preset'),
    wmStageBg: document.getElementById('wm-stage-bg'),
    wmOverlayElement: document.getElementById('wm-overlay-element'),
    wmPreviewText: document.getElementById('wm-preview-text'),
    wmPreviewImg: document.getElementById('wm-preview-img'),
    // YouTube Publish Modal Elements
    btnOpenYtPublish: document.getElementById('btn-open-yt-publish'),
    ytPublishModal: document.getElementById('yt-publish-modal'),
    btnCloseYtPublish: document.getElementById('btn-close-yt-publish'),
    ytPubTitle: document.getElementById('yt-pub-title'),
    ytPubDesc: document.getElementById('yt-pub-desc'),
    ytPubPrivacy: document.getElementById('yt-pub-privacy'),
    ytScheduleGroup: document.getElementById('yt-schedule-group'),
    ytPubScheduleDatetime: document.getElementById('yt-pub-schedule-datetime'),
    btnAiGenMeta: document.getElementById('btn-ai-gen-meta'),
    btnSubmitYtPublish: document.getElementById('btn-submit-yt-publish'),
    ytAuthNotice: document.getElementById('yt-auth-notice'),
};

// ==========================================================================
// XSS PROTECTION & DEBOUNCE
// ==========================================================================
function escapeHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

function debounce(fn, ms) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), ms);
    };
}

// ==========================================================================
// INITIALIZATION
// ==========================================================================
document.addEventListener('DOMContentLoaded', () => {
    loadSettingsIntoUI();
    setupEventListeners();
    updateSequentialBanner();
    loadWatermarkPresets();
    loadWatermarkImages();
});

function loadSettingsIntoUI() {
    el.cfgSubtitleStyle.value = state.settings.subtitleStyle;
    el.cfgLayoutMode.value = state.settings.layoutMode;
    el.cfgClipMode.value = state.settings.clipMode;
    el.cfgMaxClips.value = state.settings.maxClips;
    el.cfgClipDuration.value = state.settings.clipDuration;
    el.settingProvider.value = state.settings.provider;
    el.settingGeminiKey.value = state.settings.geminiKey;
    el.settingGroqKey.value = state.settings.groqKey;
}

function saveSettingsFromUI() {
    state.settings.provider = el.settingProvider.value;
    state.settings.geminiKey = el.settingGeminiKey.value.trim();
    state.settings.groqKey = el.settingGroqKey.value.trim();
    state.settings.subtitleStyle = el.cfgSubtitleStyle.value;
    state.settings.layoutMode = el.cfgLayoutMode.value;
    state.settings.clipMode = el.cfgClipMode.value;
    state.settings.maxClips = parseInt(el.cfgMaxClips.value, 10) || 5;
    state.settings.clipDuration = parseInt(el.cfgClipDuration.value, 10) || 60;

    persistState();
    showToast('Configurações salvas!', 'success');
    el.settingsModal.style.display = 'none';
}

function persistState() {
    for (const [key, val] of Object.entries({
        provider: state.settings.provider,
        gemini_key: state.settings.geminiKey,
        groq_key: state.settings.groqKey,
        wm_text: watermarkState.current.text,
        wm_pos: watermarkState.current.position,
        wm_type: watermarkState.current.type,
        wm_scale: watermarkState.current.scale,
        wm_opacity: watermarkState.current.opacity,
        wm_img: watermarkState.current.image_name || '',
        wm_preset_id: state.settings.watermarkPresetId,
        sub_style: state.settings.subtitleStyle,
        layout: state.settings.layoutMode,
        clip_mode: state.settings.clipMode,
        max_clips: state.settings.maxClips,
        clip_duration: state.settings.clipDuration,
    })) {
        localStorage.setItem(`autoshorts_${key}`, val);
    }
}

async function fetchStorageStats() {
    try {
        const res = await fetch('/api/storage-stats');
        if (!res.ok) return;
        const stats = await res.json();
        if (el.statDownloadsMb) el.statDownloadsMb.textContent = `${stats.downloads_mb} MB`;
        if (el.statOutputsMb) el.statOutputsMb.textContent = `${stats.outputs_mb} MB`;
    } catch (e) {
        console.warn('Erro ao obter estatísticas de disco:', e);
    }
}

async function clearDiskCache() {
    if (!confirm('Deseja apagar os vídeos fonte baixados para liberar espaço em disco?\n(Seus Shorts já gerados NÃO serão apagados)')) {
        return;
    }

    try {
        showToast('Limpando cache de vídeos fonte...', 'info');
        const res = await fetch('/api/clear-cache', { method: 'POST' });
        if (!res.ok) throw new Error('Erro ao limpar cache');

        const data = await res.json();
        showToast(`${data.freed_mb} MB liberados com sucesso! (${data.cleared_files} arquivos)`, 'success');
        fetchStorageStats();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function updateSequentialBanner() {
    const isSequential = el.cfgClipMode.value === 'sequential';
    if (el.sequentialInfoBanner) {
        el.sequentialInfoBanner.style.display = isSequential ? 'flex' : 'none';
    }
    if (isSequential) {
        const count = parseInt(el.cfgMaxClips.value, 10) || 5;
        const dur = parseInt(el.cfgClipDuration.value, 10) || 60;
        const startOffset = parseInt(el.cfgStartOffset ? el.cfgStartOffset.value : 1, 10) || 1;
        const endOffset = startOffset + count - 1;
        const minStart = Math.floor(((startOffset - 1) * dur) / 60);
        const minEnd = Math.ceil((endOffset * dur) / 60);

        if (el.seqInfoText) {
            el.seqInfoText.innerHTML = `Fatiando <strong>${count} Shorts por lote</strong> (do Short #${startOffset} ao #${endOffset}, aprox. min ${minStart} ao ${minEnd}). Sem repetições!`;
        }

        document.querySelectorAll('.btn-seq-batch').forEach(btn => {
            const bOffset = parseInt(btn.dataset.offset, 10);
            if (bOffset === startOffset) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }
}

function setupEventListeners() {
    el.cfgLayoutMode.addEventListener('change', () => {
        if (el.reactConfigPanel) {
            el.reactConfigPanel.style.display = el.cfgLayoutMode.value === 'react_split' ? 'block' : 'none';
        }
    });

    el.cfgClipMode.addEventListener('change', updateSequentialBanner);
    el.cfgMaxClips.addEventListener('input', updateSequentialBanner);
    el.cfgClipDuration.addEventListener('input', updateSequentialBanner);
    if (el.cfgStartOffset) {
        el.cfgStartOffset.addEventListener('input', updateSequentialBanner);
    }

    document.querySelectorAll('.btn-seq-batch').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const offset = parseInt(e.currentTarget.dataset.offset, 10);
            if (el.cfgStartOffset) el.cfgStartOffset.value = offset;
            updateSequentialBanner();
            if (state.currentVideo && state.currentVideo.url) {
                analyzeVideo();
            }
        });
    });

    el.btnPaste.addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text) {
                el.ytUrlInput.value = text;
                showToast('Link colado!', 'info');
            }
        } catch {
            el.ytUrlInput.focus();
        }
    });

    el.ytUrlInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !state.isAnalyzing) analyzeVideo();
    });

    el.btnAnalyze.addEventListener('click', analyzeVideo);
    if (el.btnSeqGenerateNow) el.btnSeqGenerateNow.addEventListener('click', analyzeVideo);

    el.btnOpenSettings.addEventListener('click', () => {
        fetchStorageStats();
        el.settingsModal.style.display = 'flex';
    });
    el.btnCloseSettings.addEventListener('click', () => {
        el.settingsModal.style.display = 'none';
    });
    el.btnSaveSettings.addEventListener('click', saveSettingsFromUI);
    if (el.btnClearCache) {
        el.btnClearCache.addEventListener('click', clearDiskCache);
    }

    el.btnViewLibrary.addEventListener('click', () => {
        const isHidden = el.librarySection.style.display === 'none';
        if (isHidden) {
            el.librarySection.style.display = 'block';
            el.resultsSection.style.display = 'none';
            loadLibraryOutputs();
        } else {
            el.librarySection.style.display = 'none';
            if (state.currentClips.length > 0) {
                el.resultsSection.style.display = 'block';
            }
        }
    });

    el.btnRefreshLibrary.addEventListener('click', debounce(loadLibraryOutputs, 500));
    el.btnClosePreview.addEventListener('click', closePreviewModal);

    el.btnCopyTitle.addEventListener('click', () => {
        const title = el.previewTitle.textContent;
        navigator.clipboard.writeText(title).then(() => {
            showToast('Título copiado!', 'success');
        }).catch(() => {
            showToast('Falha ao copiar', 'error');
        });
    });

    if (el.btnGenerateAll) {
        el.btnGenerateAll.addEventListener('click', generateAllShorts);
    }

    // YouTube Publish Event Listeners
    if (el.btnOpenYtPublish) {
        el.btnOpenYtPublish.addEventListener('click', openYtPublishModalFromPreview);
    }
    if (el.btnCloseYtPublish) {
        el.btnCloseYtPublish.addEventListener('click', closeYtPublishModal);
    }
    if (el.ytPubPrivacy) {
        el.ytPubPrivacy.addEventListener('change', () => {
            el.ytScheduleGroup.style.display = el.ytPubPrivacy.value === 'scheduled' ? 'block' : 'none';
        });
    }
    if (el.btnAiGenMeta) {
        el.btnAiGenMeta.addEventListener('click', generateAiMetadataForPublish);
    }
    if (el.btnSubmitYtPublish) {
        el.btnSubmitYtPublish.addEventListener('click', submitYoutubePublish);
    }

    // Watermark Editor Event Listeners
    el.btnOpenWmEditor.addEventListener('click', openWmEditorModal);
    el.btnCloseWmEditor.addEventListener('click', closeWmEditorModal);
    el.cfgWmPreset.addEventListener('change', onPresetChangeInWorkspace);

    el.wmTypeSelect.addEventListener('change', onWmTypeChange);
    el.wmTextInput.addEventListener('input', updateWmLivePreview);
    el.wmImageSelect.addEventListener('change', updateWmLivePreview);
    el.wmPosSelect.addEventListener('change', updateWmLivePreview);
    el.wmScaleRange.addEventListener('input', () => {
        el.wmScaleVal.textContent = `${el.wmScaleRange.value}px`;
        updateWmLivePreview();
    });
    el.wmOpacityRange.addEventListener('input', () => {
        const pct = Math.round(parseFloat(el.wmOpacityRange.value) * 100);
        el.wmOpacityVal.textContent = `${pct}%`;
        updateWmLivePreview();
    });

    el.btnUploadWmFile.addEventListener('click', () => el.wmFileInput.click());
    el.wmFileInput.addEventListener('change', handleWmFileUpload);
    el.btnSaveWmPreset.addEventListener('click', saveCurrentWatermarkPreset);

    window.addEventListener('click', (e) => {
        if (e.target === el.settingsModal) el.settingsModal.style.display = 'none';
        if (e.target === el.previewModal) closePreviewModal();
        if (e.target === el.wmEditorModal) closeWmEditorModal();
    });

    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (el.previewModal.style.display !== 'none') closePreviewModal();
            if (el.settingsModal.style.display !== 'none') el.settingsModal.style.display = 'none';
            if (el.wmEditorModal.style.display !== 'none') closeWmEditorModal();
        }
    });
}

// ==========================================================================
// WATERMARK & PRESETS MANAGEMENT
// ==========================================================================
async function loadWatermarkPresets() {
    try {
        const res = await fetch('/api/watermark-presets');
        if (!res.ok) return;
        watermarkState.presets = await res.json();
        renderPresetDropdown();
    } catch (e) {
        console.warn('Erro ao carregar presets:', e);
    }
}

async function loadWatermarkImages() {
    try {
        const res = await fetch('/api/watermarks');
        if (!res.ok) return;
        watermarkState.images = await res.json();
        renderWmImageDropdown();
    } catch (e) {
        console.warn('Erro ao carregar imagens:', e);
    }
}

function renderPresetDropdown() {
    el.cfgWmPreset.innerHTML = '';
    watermarkState.presets.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = `${p.name}`;
        if (p.id === state.settings.watermarkPresetId) opt.selected = true;
        el.cfgWmPreset.appendChild(opt);
    });

    const customOpt = document.createElement('option');
    customOpt.value = 'custom';
    customOpt.textContent = '✏️ Personalizado (Editar no 9:16)...';
    if (state.settings.watermarkPresetId === 'custom') customOpt.selected = true;
    el.cfgWmPreset.appendChild(customOpt);

    // Sync current preset
    applySelectedPreset(state.settings.watermarkPresetId);
}

function renderWmImageDropdown() {
    el.wmImageSelect.innerHTML = '<option value="">-- Selecione uma Imagem --</option>';
    watermarkState.images.forEach(img => {
        const opt = document.createElement('option');
        opt.value = img.filename;
        opt.textContent = `${img.filename} (${img.size_kb} KB)`;
        if (img.filename === watermarkState.current.image_name) opt.selected = true;
        el.wmImageSelect.appendChild(opt);
    });
}

function onPresetChangeInWorkspace() {
    const selectedId = el.cfgWmPreset.value;
    state.settings.watermarkPresetId = selectedId;
    applySelectedPreset(selectedId);
    persistState();
}

function applySelectedPreset(presetId) {
    if (presetId === 'custom') return;
    const preset = watermarkState.presets.find(p => p.id === presetId);
    if (!preset) return;

    watermarkState.current = {
        type: preset.type || 'text',
        text: preset.text || '@meucanal',
        position: preset.position || 'top_right',
        scale: preset.scale || 250,
        opacity: preset.opacity || 0.9,
        image_name: preset.image_name || null
    };

    // Update modal controls if open
    syncModalControlsFromState();
}

function openWmEditorModal() {
    syncModalControlsFromState();
    updateWmLivePreview();
    el.wmEditorModal.style.display = 'flex';
}

function closeWmEditorModal() {
    el.wmEditorModal.style.display = 'none';
}

function syncModalControlsFromState() {
    const curr = watermarkState.current;
    el.wmTypeSelect.value = curr.type;
    el.wmTextInput.value = curr.text;
    el.wmPosSelect.value = curr.position;
    el.wmScaleRange.value = curr.scale;
    el.wmScaleVal.textContent = `${curr.scale}px`;
    el.wmOpacityRange.value = curr.opacity;
    el.wmOpacityVal.textContent = `${Math.round(curr.opacity * 100)}%`;

    if (curr.image_name && el.wmImageSelect) {
        el.wmImageSelect.value = curr.image_name;
    }

    onWmTypeChange();
}

function onWmTypeChange() {
    const type = el.wmTypeSelect.value;
    watermarkState.current.type = type;

    if (type === 'text') {
        el.wmTextGroup.style.display = 'block';
        el.wmImageGroup.style.display = 'none';
        el.wmScaleGroup.style.display = 'block';
    } else if (type === 'image') {
        el.wmTextGroup.style.display = 'none';
        el.wmImageGroup.style.display = 'block';
        el.wmScaleGroup.style.display = 'block';
    } else { // full_overlay
        el.wmTextGroup.style.display = 'none';
        el.wmImageGroup.style.display = 'block';
        el.wmScaleGroup.style.display = 'none';
        el.wmPosSelect.value = 'full_916';
    }

    updateWmLivePreview();
}

function updateWmLivePreview() {
    const type = el.wmTypeSelect.value;
    const text = el.wmTextInput.value.trim() || '@meucanal';
    const imgName = el.wmImageSelect.value;
    const pos = el.wmPosSelect.value;
    const scale = parseInt(el.wmScaleRange.value, 10) || 250;
    const opacity = parseFloat(el.wmOpacityRange.value) || 0.9;

    watermarkState.current = {
        type,
        text,
        position: pos,
        scale,
        opacity,
        image_name: imgName
    };

    const overlayEl = el.wmOverlayElement;
    overlayEl.style.opacity = opacity;

    // Type display
    if (type === 'text') {
        el.wmPreviewText.style.display = 'inline-block';
        el.wmPreviewImg.style.display = 'none';
        el.wmPreviewText.textContent = text;
        const fontSz = Math.max(10, Math.round((scale / 1080) * 45));
        el.wmPreviewText.style.fontSize = `${fontSz}px`;
    } else {
        el.wmPreviewText.style.display = 'none';
        el.wmPreviewImg.style.display = 'block';
        const activeImg = imgName || (type === 'full_overlay' ? 'gato_galudo_overlay.png' : '');
        if (activeImg) {
            el.wmPreviewImg.src = `/storage/watermarks/${activeImg}`;
        } else {
            el.wmPreviewImg.src = '';
        }
    }

    // Positioning on 270x480 preview phone frame
    overlayEl.style.top = '';
    overlayEl.style.bottom = '';
    overlayEl.style.left = '';
    overlayEl.style.right = '';
    overlayEl.style.transform = '';
    overlayEl.style.width = '';
    overlayEl.style.height = '';

    if (pos === 'full_916' || type === 'full_overlay') {
        overlayEl.style.top = '0';
        overlayEl.style.left = '0';
        overlayEl.style.width = '100%';
        overlayEl.style.height = '100%';
        el.wmPreviewImg.style.width = '100%';
        el.wmPreviewImg.style.height = '100%';
        el.wmPreviewImg.style.objectFit = 'contain';
    } else {
        const previewScalePx = Math.round((scale / 1080) * 270);
        if (type === 'image') {
            el.wmPreviewImg.style.width = `${previewScalePx}px`;
        }

        switch (pos) {
            case 'top_left':
                overlayEl.style.top = '15px';
                overlayEl.style.left = '15px';
                break;
            case 'top_center':
                overlayEl.style.top = '15px';
                overlayEl.style.left = '50%';
                overlayEl.style.transform = 'translateX(-50%)';
                break;
            case 'top_right':
                overlayEl.style.top = '15px';
                overlayEl.style.right = '15px';
                break;
            case 'bottom_left':
                overlayEl.style.bottom = '40px';
                overlayEl.style.left = '15px';
                break;
            case 'bottom_center':
                overlayEl.style.bottom = '50px';
                overlayEl.style.left = '50%';
                overlayEl.style.transform = 'translateX(-50%)';
                break;
            case 'bottom_right':
                overlayEl.style.bottom = '40px';
                overlayEl.style.right = '15px';
                break;
            case 'center':
                overlayEl.style.top = '50%';
                overlayEl.style.left = '50%';
                overlayEl.style.transform = 'translate(-50%, -50%)';
                break;
            default:
                overlayEl.style.top = '15px';
                overlayEl.style.right = '15px';
        }
    }
}

async function handleWmFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        showToast('Enviando marca d\'água...', 'info');
        const res = await fetch('/api/upload-watermark', {
            method: 'POST',
            body: formData
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Erro no upload' }));
            throw new Error(err.detail || 'Falha ao enviar arquivo');
        }

        const data = await res.json();
        showToast('Imagem enviada com sucesso!', 'success');
        await loadWatermarkImages();

        el.wmImageSelect.value = data.filename;
        updateWmLivePreview();

    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function saveCurrentWatermarkPreset() {
    const presetName = el.wmPresetNameInput.value.trim() || 'Predefinição Personalizada';
    const curr = watermarkState.current;

    const presetPayload = {
        name: presetName,
        type: curr.type,
        text: curr.text,
        position: curr.position,
        scale: curr.scale,
        opacity: curr.opacity,
        image_name: curr.image_name,
        badge: curr.type === 'full_overlay' ? 'Overlay 9:16' : (curr.type === 'image' ? 'Imagem' : 'Texto')
    };

    try {
        const res = await fetch('/api/watermark-presets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(presetPayload)
        });

        if (!res.ok) throw new Error('Erro ao salvar predefinição.');

        const data = await res.json();
        showToast('Predefinição salva com sucesso!', 'success');
        await loadWatermarkPresets();

        el.cfgWmPreset.value = data.preset.id;
        state.settings.watermarkPresetId = data.preset.id;
        persistState();
        closeWmEditorModal();

    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ==========================================================================
// ANALYSIS
// ==========================================================================
async function analyzeVideo() {
    if (state.isAnalyzing) return;

    const url = el.ytUrlInput.value.trim();
    if (!url) {
        showToast('Insira o link de um vídeo do YouTube.', 'error');
        el.ytUrlInput.focus();
        return;
    }

    const clipMode = el.cfgClipMode.value;
    const maxClips = parseInt(el.cfgMaxClips.value, 10) || 5;
    const clipDuration = parseInt(el.cfgClipDuration.value, 10) || 60;

    let minDur, maxDur;
    if (clipMode === 'sequential') {
        minDur = clipDuration;
        maxDur = clipDuration;
    } else {
        minDur = Math.max(15, Math.floor(clipDuration * 0.5));
        maxDur = clipDuration;
    }

    state.isAnalyzing = true;
    setAnalyzeLoading(true);

    const modeLabel = clipMode === 'sequential' ? 'Fatiando vídeo sequencialmente...' : 'Obtendo transcrição e analisando cortes virais...';
    showToast(modeLabel, 'info');

    if (state.activeAbortController) state.activeAbortController.abort();
    state.activeAbortController = new AbortController();

    try {
        const res = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url,
                gemini_api_key: state.settings.geminiKey || null,
                groq_api_key: state.settings.groqKey || null,
                min_duration: minDur,
                max_duration: maxDur,
                max_clips: maxClips,
                provider: state.settings.provider,
                clip_mode: clipMode,
                start_clip_offset: parseInt(el.cfgStartOffset ? el.cfgStartOffset.value : 1, 10) || 1,
            }),
            signal: state.activeAbortController.signal
        });

        if (!res.ok) {
            const errData = await res.json().catch(() => ({ detail: 'Erro desconhecido' }));
            throw new Error(errData.detail || 'Falha ao analisar vídeo.');
        }

        const data = await res.json();
        state.currentVideo = data.metadata;
        state.currentClips = data.clips;

        if (data.genre_info && data.genre_info.is_react) {
            if (el.reactAlertBanner) {
                el.reactAlertBanner.style.display = 'flex';
                if (el.reactAlertTitle) el.reactAlertTitle.textContent = data.genre_info.badge || 'Vídeo de React Detectado!';
                if (el.reactAlertText) el.reactAlertText.innerHTML = `${escapeHtml(data.genre_info.tip)} O formato <strong>Split-Screen (Câmera + Conteúdo)</strong> foi selecionado automaticamente.`;
            }
            el.cfgLayoutMode.value = 'react_split';
            if (el.reactConfigPanel) el.reactConfigPanel.style.display = 'block';
            if (el.cfgReactCamPos && data.genre_info.suggested_cam_pos) {
                el.cfgReactCamPos.value = data.genre_info.suggested_cam_pos;
            }
        } else {
            if (el.reactAlertBanner) el.reactAlertBanner.style.display = 'none';
            if (el.reactConfigPanel && el.cfgLayoutMode.value !== 'react_split') {
                el.reactConfigPanel.style.display = 'none';
            }
        }

        renderVideoMetadata(data.metadata, data.total_segments, data.clips.length, data.genre_info);
        renderClipsGrid(data.clips);

        if (el.btnGenerateAll) {
            el.btnGenerateAll.style.display = data.clips.length >= 2 ? 'flex' : 'none';
            el.btnGenerateAll.querySelector('span').textContent = `Gerar Todos os ${data.clips.length} Shorts`;
        }

        el.resultsSection.style.display = 'block';
        el.librarySection.style.display = 'none';
        el.resultsSection.scrollIntoView({ behavior: 'smooth' });
        showToast(`${data.clips.length} cortes identificados!`, 'success');

    } catch (err) {
        if (err.name !== 'AbortError') {
            showToast(err.message, 'error');
        }
    } finally {
        state.isAnalyzing = false;
        setAnalyzeLoading(false);
    }
}

function setAnalyzeLoading(isLoading) {
    el.btnAnalyze.disabled = isLoading;
    el.analyzeSpinner.style.display = isLoading ? 'block' : 'none';
    const btnText = el.btnAnalyze.querySelector('.btn-text');
    if (btnText) {
        btnText.innerHTML = isLoading
            ? '<i class="ri-loader-4-line ri-spin"></i> Processando IA...'
            : '<i class="ri-magic-line"></i> Encontrar Cortes Virais';
    }
}

function renderVideoMetadata(meta, totalSegments, totalClips, genreInfo) {
    el.metaThumb.src = meta.thumbnail || '';
    el.metaThumb.alt = escapeHtml(meta.title || 'Thumbnail');
    el.metaTitle.textContent = meta.title || 'Video';
    el.metaChannel.textContent = meta.channel || 'YouTube';
    el.metaDuration.textContent = formatTime(meta.duration);
    el.metaClipsCount.textContent = totalClips;
    el.metaTranscriptCount.textContent = totalSegments;

    let engineName = 'Motor Local Gratuito';
    if (state.settings.geminiKey) engineName = 'Gemini 2.0 Flash';
    else if (state.settings.groqKey) engineName = 'Groq Llama 3';
    el.metaEngineUsed.innerHTML = `<i class="ri-cpu-line"></i> ${escapeHtml(engineName)}`;

    if (el.metaGenreBadge) {
        const badgeText = genreInfo ? genreInfo.badge : '✨ Vídeo Geral';
        const icon = genreInfo && genreInfo.is_react ? 'ri-video-chat-line' : 'ri-movie-line';
        el.metaGenreBadge.innerHTML = `<i class="${icon}"></i> ${escapeHtml(badgeText)}`;
    }
}

function renderClipsGrid(clips) {
    el.clipsGrid.innerHTML = '';

    clips.forEach((clip) => {
        const card = document.createElement('div');
        card.className = 'clip-card';
        card.id = `clip-card-${clip.id}`;

        const scoreClass = clip.score >= 90 ? 'score-ultra' : 'score-high';
        const scoreIcon = clip.score >= 90 ? 'Viral Máximo' : 'Alta Retenção';

        card.innerHTML = `
            <div class="clip-card-header">
                <span class="viral-score-badge ${scoreClass}">
                    <i class="ri-fire-fill"></i> ${escapeHtml(scoreIcon)} &bull; ${clip.score}/100
                </span>
                <span class="clip-duration-tag">
                    <i class="ri-timer-line"></i> <span id="dur-label-${clip.id}">${clip.duration}s</span>
                </span>
            </div>
            <input type="text" class="clip-title-input" id="title-${clip.id}" value="${escapeHtml(clip.title)}" placeholder="Título do Short">
            <div class="clip-hook-box">
                <div class="hook-label"><i class="ri-focus-2-line"></i> Gancho Inicial (0s a 4s):</div>
                "${escapeHtml(clip.hook)}"
            </div>
            <div class="time-trim-box">
                <div class="trim-group">
                    <label>Início (s):</label>
                    <input type="number" step="0.5" class="trim-input" id="start-${clip.id}" value="${clip.start}">
                </div>
                <i class="ri-arrow-right-line" style="color: var(--text-muted);"></i>
                <div class="trim-group">
                    <label>Fim (s):</label>
                    <input type="number" step="0.5" class="trim-input" id="end-${clip.id}" value="${clip.end}">
                </div>
            </div>
            <details class="clip-snippet-accordion">
                <summary class="snippet-summary">Ver fala transcrita deste trecho</summary>
                <div class="snippet-text">${escapeHtml(clip.transcript_snippet || 'Texto da transcrição.')}</div>
            </details>
            <div class="clip-card-footer">
                <button class="btn-primary btn-generate-card" id="btn-gen-${clip.id}">
                    <i class="ri-movie-fill"></i> Gerar Short Vertical 9:16
                </button>
            </div>
        `;

        const startInput = card.querySelector(`#start-${clip.id}`);
        const endInput = card.querySelector(`#end-${clip.id}`);
        const durLabel = card.querySelector(`#dur-label-${clip.id}`);

        const updateDur = () => {
            const s = parseFloat(startInput.value) || 0;
            const e = parseFloat(endInput.value) || 0;
            durLabel.textContent = `${Math.max(0, e - s).toFixed(1)}s`;
        };
        startInput.addEventListener('input', updateDur);
        endInput.addEventListener('input', updateDur);

        card.querySelector(`#btn-gen-${clip.id}`).addEventListener('click', () => {
            if (state.isGenerating) {
                showToast('Aguarde a geração atual finalizar.', 'info');
                return;
            }
            const titleVal = card.querySelector(`#title-${clip.id}`).value;
            const startVal = parseFloat(startInput.value);
            const endVal = parseFloat(endInput.value);
            generateSingleShort(clip.id, titleVal, startVal, endVal);
        });

        el.clipsGrid.appendChild(card);
    });
}

// ==========================================================================
// SHORT GENERATION & PROGRESS (SINGLE & BATCH)
// ==========================================================================
async function generateSingleShort(clipId, title, start, end) {
    if (end <= start) {
        showToast('O tempo final deve ser maior que o inicial.', 'error');
        return;
    }

    state.isGenerating = true;
    state.isBatchMode = false;
    openProgressModal(false);

    const wm = watermarkState.current;
    const activeWmImg = wm.image_name || (wm.type === 'full_overlay' ? 'gato_galudo_overlay.png' : null);

    try {
        const payload = {
            url: state.currentVideo.url,
            clip_id: clipId,
            start,
            end,
            title,
            layout: el.cfgLayoutMode.value,
            subtitle_style: el.cfgSubtitleStyle.value,
            watermark_type: wm.type,
            watermark_text: wm.text,
            watermark_position: wm.position,
            watermark_image_name: activeWmImg,
            watermark_scale: wm.scale,
            watermark_opacity: wm.opacity,
            react_cam_pos: el.cfgReactCamPos ? el.cfgReactCamPos.value : 'bottom_right',
            react_cam_order: el.cfgReactCamOrder ? el.cfgReactCamOrder.value : 'cam_top_content_bottom',
            react_ratio: el.cfgReactRatio ? el.cfgReactRatio.value : '50_50'
        };

        const res = await fetch('/api/generate-short', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Erro desconhecido' }));
            throw new Error(err.detail || 'Erro ao iniciar geração.');
        }

        const data = await res.json();
        state.activeTaskId = data.task_id;
        startProgressPolling(data.task_id, title);

    } catch (err) {
        closeProgressModal();
        showToast(err.message, 'error');
        state.isGenerating = false;
    }
}

async function generateAllShorts() {
    if (state.isGenerating) {
        showToast('Aguarde a geração atual finalizar.', 'info');
        return;
    }

    if (!state.currentClips || state.currentClips.length === 0) {
        showToast('Nenhum corte disponível para gerar.', 'error');
        return;
    }

    const clipsData = [];
    for (const clip of state.currentClips) {
        const titleEl = document.getElementById(`title-${clip.id}`);
        const startEl = document.getElementById(`start-${clip.id}`);
        const endEl = document.getElementById(`end-${clip.id}`);

        clipsData.push({
            clip_id: clip.id,
            title: titleEl ? titleEl.value : clip.title,
            start: startEl ? parseFloat(startEl.value) : clip.start,
            end: endEl ? parseFloat(endEl.value) : clip.end,
        });
    }

    state.isGenerating = true;
    state.isBatchMode = true;
    openProgressModal(true, clipsData.length);

    const wm = watermarkState.current;
    const activeWmImg = wm.image_name || (wm.type === 'full_overlay' ? 'gato_galudo_overlay.png' : null);

    try {
        const payload = {
            url: state.currentVideo.url,
            clips: clipsData,
            layout: el.cfgLayoutMode.value,
            subtitle_style: el.cfgSubtitleStyle.value,
            watermark_type: wm.type,
            watermark_text: wm.text,
            watermark_position: wm.position,
            watermark_image_name: activeWmImg,
            watermark_scale: wm.scale,
            watermark_opacity: wm.opacity,
            react_cam_pos: el.cfgReactCamPos ? el.cfgReactCamPos.value : 'bottom_right',
            react_cam_order: el.cfgReactCamOrder ? el.cfgReactCamOrder.value : 'cam_top_content_bottom',
            react_ratio: el.cfgReactRatio ? el.cfgReactRatio.value : '50_50',
        };

        const res = await fetch('/api/generate-batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Erro desconhecido' }));
            throw new Error(err.detail || 'Erro ao iniciar geração em lote.');
        }

        const data = await res.json();
        state.activeTaskId = data.task_id;
        startBatchProgressPolling(data.task_id, clipsData.length);

    } catch (err) {
        closeProgressModal();
        showToast(err.message, 'error');
        state.isGenerating = false;
        state.isBatchMode = false;
    }
}

// ==========================================================================
// PROGRESS MODAL & POLLING
// ==========================================================================
function openProgressModal(isBatch = false, totalClips = 0) {
    el.progressModal.style.display = 'flex';
    el.progressBarFill.style.width = '2%';
    el.progressPercentage.textContent = '2%';
    el.progressStatusText.textContent = isBatch
        ? `Iniciando geração em lote de ${totalClips} shorts...`
        : 'Iniciando pipeline de vídeo...';
    el.progressStageStep.textContent = 'Etapa 1 de 4';
    [el.stepSubs, el.stepDownload, el.stepRender, el.stepFinish].forEach(s => s.className = 'step-item');
    el.stepSubs.classList.add('active');

    if (el.batchProgressInfo) {
        el.batchProgressInfo.style.display = isBatch ? 'flex' : 'none';
        if (isBatch) {
            el.batchCounterText.textContent = `Short 0 de ${totalClips}`;
            el.batchMiniBarFill.style.width = '0%';
        }
    }
}

function closeProgressModal() {
    el.progressModal.style.display = 'none';
    if (state.pollInterval) {
        clearInterval(state.pollInterval);
        state.pollInterval = null;
    }
    state.isBatchMode = false;
    if (el.batchProgressInfo) {
        el.batchProgressInfo.style.display = 'none';
    }
}

function startProgressPolling(taskId, title) {
    if (state.pollInterval) clearInterval(state.pollInterval);

    let consecutiveErrors = 0;

    state.pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/progress/${taskId}`);
            if (!res.ok) {
                consecutiveErrors++;
                if (consecutiveErrors > 10) {
                    clearInterval(state.pollInterval);
                    state.pollInterval = null;
                    closeProgressModal();
                    showToast('Servidor indisponível. Tente novamente.', 'error');
                    state.isGenerating = false;
                }
                return;
            }
            consecutiveErrors = 0;

            const task = await res.json();
            updateProgressUI(task);

            if (task.status === 'completed') {
                clearInterval(state.pollInterval);
                state.pollInterval = null;
                state.isGenerating = false;
                setTimeout(() => {
                    closeProgressModal();
                    openPreviewModal(task.result);
                    showToast('Short renderizado com sucesso!', 'success');
                }, 600);
            } else if (task.status === 'error') {
                clearInterval(state.pollInterval);
                state.pollInterval = null;
                state.isGenerating = false;
                closeProgressModal();
                showToast(`Erro: ${task.error || 'Desconhecido'}`, 'error');
            }
        } catch {
            consecutiveErrors++;
        }
    }, 1000);
}

function startBatchProgressPolling(taskId, totalClips) {
    if (state.pollInterval) clearInterval(state.pollInterval);

    let consecutiveErrors = 0;

    state.pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/progress/${taskId}`);
            if (!res.ok) {
                consecutiveErrors++;
                if (consecutiveErrors > 15) {
                    clearInterval(state.pollInterval);
                    state.pollInterval = null;
                    closeProgressModal();
                    showToast('Servidor indisponível. Tente novamente.', 'error');
                    state.isGenerating = false;
                    state.isBatchMode = false;
                }
                return;
            }
            consecutiveErrors = 0;

            const task = await res.json();

            const batchCurrent = task.batch_current || 0;
            const batchTotal = task.batch_total || totalClips;
            const batchCompleted = task.batch_completed || 0;

            el.progressBarFill.style.width = `${task.progress || 0}%`;
            el.progressPercentage.textContent = `${task.progress || 0}%`;
            el.progressStatusText.textContent = task.message || 'Processando lote...';

            if (el.batchCounterText) {
                el.batchCounterText.textContent = `Short ${batchCurrent} de ${batchTotal}`;
            }
            if (el.batchMiniBarFill) {
                const miniPct = batchTotal > 0 ? Math.round((batchCompleted / batchTotal) * 100) : 0;
                el.batchMiniBarFill.style.width = `${miniPct}%`;
            }

            const pct = task.progress || 0;
            if (pct < 20) {
                el.progressStageStep.textContent = `Preparando Short ${batchCurrent}/${batchTotal}`;
                el.stepSubs.className = 'step-item active';
            } else if (pct < 50) {
                el.stepSubs.className = 'step-item done';
                el.stepDownload.className = 'step-item active';
                el.progressStageStep.textContent = `Processando Short ${batchCurrent}/${batchTotal}`;
            } else if (pct < 95) {
                el.stepSubs.className = 'step-item done';
                el.stepDownload.className = 'step-item done';
                el.stepRender.className = 'step-item active';
                el.progressStageStep.textContent = `Renderizando Short ${batchCurrent}/${batchTotal}`;
            } else {
                el.stepSubs.className = 'step-item done';
                el.stepDownload.className = 'step-item done';
                el.stepRender.className = 'step-item done';
                el.stepFinish.className = 'step-item active';
                el.progressStageStep.textContent = 'Finalizando lote...';
            }

            if (task.status === 'completed') {
                clearInterval(state.pollInterval);
                state.pollInterval = null;
                state.isGenerating = false;
                state.isBatchMode = false;
                setTimeout(() => {
                    closeProgressModal();
                    const result = task.result || {};
                    const successCount = result.success_count || 0;
                    const totalCount = result.total || totalClips;
                    showToast(`${successCount}/${totalCount} shorts gerados com sucesso! Confira na Biblioteca.`, 'success');

                    if (el.cfgClipMode.value === 'sequential' && el.cfgStartOffset) {
                        const currentOff = parseInt(el.cfgStartOffset.value, 10) || 1;
                        const nextOff = currentOff + totalCount;
                        el.cfgStartOffset.value = nextOff;
                        updateSequentialBanner();
                        showToast(`Próximo lote configurado a partir do Short #${nextOff}!`, 'info');
                    }

                    el.librarySection.style.display = 'block';
                    el.resultsSection.style.display = 'none';
                    loadLibraryOutputs();
                }, 800);
            } else if (task.status === 'error') {
                clearInterval(state.pollInterval);
                state.pollInterval = null;
                state.isGenerating = false;
                state.isBatchMode = false;
                closeProgressModal();
                showToast(`Erro no lote: ${task.error || 'Desconhecido'}`, 'error');
            }
        } catch {
            consecutiveErrors++;
        }
    }, 1500);
}

function updateProgressUI(task) {
    const pct = task.progress || 0;
    el.progressBarFill.style.width = `${pct}%`;
    el.progressPercentage.textContent = `${pct}%`;
    el.progressStatusText.textContent = task.message || 'Processando...';

    if (pct < 30) {
        el.stepSubs.className = 'step-item active';
        el.progressStageStep.textContent = 'Etapa 1 de 4';
    } else if (pct < 55) {
        el.stepSubs.className = 'step-item done';
        el.stepDownload.className = 'step-item active';
        el.progressStageStep.textContent = 'Etapa 2 de 4';
    } else if (pct < 95) {
        el.stepSubs.className = 'step-item done';
        el.stepDownload.className = 'step-item done';
        el.stepRender.className = 'step-item active';
        el.progressStageStep.textContent = 'Etapa 3 de 4';
    } else {
        el.stepSubs.className = 'step-item done';
        el.stepDownload.className = 'step-item done';
        el.stepRender.className = 'step-item done';
        el.stepFinish.className = 'step-item active';
        el.progressStageStep.textContent = 'Etapa 4 de 4';
    }
}

// ==========================================================================
// PREVIEW & LIBRARY & YOUTUBE PUBLISH
// ==========================================================================
function openPreviewModal(result) {
    state.activePublishResult = result;
    el.previewTitle.textContent = result.title || 'Short Viral';
    el.previewMeta.textContent = `Duração: ${result.duration}s | Formato: Vertical 9:16 (1080x1920)`;
    el.previewVideo.src = result.video_url;
    el.previewVideo.load();
    el.previewVideo.play().catch(() => {});
    el.btnDownloadShort.href = result.download_url;
    el.btnDownloadShort.setAttribute('download', result.filename);
    el.previewModal.style.display = 'flex';
}

function closePreviewModal() {
    el.previewVideo.pause();
    el.previewVideo.src = '';
    el.previewModal.style.display = 'none';
}

function openYtPublishModalFromPreview() {
    if (!state.activePublishResult || !state.activePublishResult.filename) {
        showToast('Nenhum vídeo selecionado para publicar.', 'error');
        return;
    }
    openYtPublishModal(state.activePublishResult.filename, state.activePublishResult.title || 'Short Viral');
}

function openYtPublishModal(filename, title) {
    state.activePublishFilename = filename;
    el.ytPubTitle.value = title || '';
    el.ytPubDesc.value = '';
    el.ytPubPrivacy.value = 'public';
    el.ytScheduleGroup.style.display = 'none';

    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(15, 0, 0, 0);
    const localIso = new Date(tomorrow.getTime() - (tomorrow.getTimezoneOffset() * 60000)).toISOString().slice(0, 16);
    el.ytPubScheduleDatetime.value = localIso;

    el.ytPublishModal.style.display = 'flex';
    generateAiMetadataForPublish();
}

function closeYtPublishModal() {
    el.ytPublishModal.style.display = 'none';
}

async function generateAiMetadataForPublish() {
    const baseTitle = el.ytPubTitle.value.trim() || 'Short Viral';
    try {
        showToast('Gerando título viral e hashtags com IA...', 'info');
        const res = await fetch('/api/youtube/generate-metadata', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                base_title: baseTitle,
                gemini_api_key: state.settings.geminiKey || null,
                groq_api_key: state.settings.groqKey || null
            })
        });

        if (!res.ok) throw new Error('Falha ao gerar metadados.');

        const data = await res.json();
        if (data.title) el.ytPubTitle.value = data.title;
        if (data.description) el.ytPubDesc.value = data.description;
        showToast('Metadados virais gerados!', 'success');
    } catch (e) {
        console.warn('Erro ao gerar metadados:', e);
    }
}

async function submitYoutubePublish() {
    const filename = state.activePublishFilename;
    if (!filename) {
        showToast('Selecione um vídeo para publicar.', 'error');
        return;
    }

    const title = el.ytPubTitle.value.trim();
    if (!title) {
        showToast('Insira um título para o vídeo.', 'error');
        el.ytPubTitle.focus();
        return;
    }

    const description = el.ytPubDesc.value.trim();
    const privacy = el.ytPubPrivacy.value;
    let publishAtIso = null;

    if (privacy === 'scheduled') {
        const dtVal = el.ytPubScheduleDatetime.value;
        if (!dtVal) {
            showToast('Selecione a data e hora para o agendamento.', 'error');
            return;
        }
        publishAtIso = new Date(dtVal).toISOString();
    }

    el.btnSubmitYtPublish.disabled = true;
    el.btnSubmitYtPublish.innerHTML = '<i class="ri-loader-4-line ri-spin"></i> Enviando para o YouTube...';
    showToast('Iniciando upload para o YouTube Shorts...', 'info');

    try {
        const res = await fetch('/api/youtube/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename,
                title,
                description,
                privacy_status: privacy === 'scheduled' ? 'private' : privacy,
                publish_at_iso: publishAtIso
            })
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: 'Erro ao enviar para o YouTube' }));
            throw new Error(err.detail || 'Falha na publicação.');
        }

        const data = await res.json();
        showToast(privacy === 'scheduled' ? 'Short agendado com sucesso no YouTube!' : 'Short publicado no YouTube com sucesso!', 'success');
        closeYtPublishModal();

        if (data.youtube_url) {
            window.open(data.youtube_url, '_blank');
        }

    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        el.btnSubmitYtPublish.disabled = false;
        el.btnSubmitYtPublish.innerHTML = '<i class="ri-upload-cloud-fill"></i> <span>Enviar para o YouTube Shorts</span>';
    }
}

async function loadLibraryOutputs() {
    try {
        const res = await fetch('/api/outputs');
        if (!res.ok) return;

        const files = await res.json();
        el.libraryGrid.innerHTML = '';

        if (files.length === 0) {
            el.libraryGrid.innerHTML = `
                <div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-muted);">
                    <i class="ri-folder-open-line" style="font-size:48px;margin-bottom:12px;display:block;"></i>
                    Nenhum Short gerado ainda. Cole um vídeo acima para começar!
                </div>`;
            return;
        }

        files.forEach(file => {
            const card = document.createElement('div');
            card.className = 'library-card glass-panel';
            const dateStr = new Date(file.created_at * 1000).toLocaleString('pt-BR');

            card.innerHTML = `
                <div class="library-card-header">
                    <span>${dateStr}</span>
                    <span>${file.size_mb} MB</span>
                </div>
                <div class="library-card-title" title="${escapeHtml(file.filename)}">${escapeHtml(file.filename)}</div>
                <div class="library-card-actions">
                    <button class="btn-primary btn-play-lib">
                        <i class="ri-play-fill"></i> Assistir
                    </button>
                    <button class="btn-secondary btn-pub-lib" style="color:#ff4d4d;">
                        <i class="ri-youtube-fill"></i> Publicar
                    </button>
                    <a class="btn-secondary" href="${file.download_url}" download="${escapeHtml(file.filename)}">
                        <i class="ri-download-line"></i> Baixar
                    </a>
                    <button class="btn-delete-lib" title="Excluir Short">
                        <i class="ri-delete-bin-line"></i>
                    </button>
                </div>`;

            card.querySelector('.btn-play-lib').addEventListener('click', () => {
                openPreviewModal({
                    title: file.filename,
                    duration: 'Finalizado',
                    video_url: file.stream_url,
                    download_url: file.download_url,
                    filename: file.filename
                });
            });

            card.querySelector('.btn-pub-lib').addEventListener('click', () => {
                openYtPublishModal(file.filename, file.filename);
            });

            card.querySelector('.btn-delete-lib').addEventListener('click', async () => {
                if (confirm(`Excluir ${file.filename}?`)) {
                    await fetch(`/api/outputs/${encodeURIComponent(file.filename)}`, { method: 'DELETE' });
                    showToast('Short excluído!', 'info');
                    loadLibraryOutputs();
                }
            });

            el.libraryGrid.appendChild(card);
        });
    } catch {
        showToast('Erro ao carregar biblioteca.', 'error');
    }
}

// ==========================================================================
// UTILITIES
// ==========================================================================
function formatTime(seconds) {
    if (!seconds) return '00:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = {
        success: 'ri-checkbox-circle-fill',
        error: 'ri-error-warning-fill',
        info: 'ri-information-fill'
    };

    toast.innerHTML = `<i class="${icons[type] || icons.info}"></i> <span>${escapeHtml(message)}</span>`;
    el.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
