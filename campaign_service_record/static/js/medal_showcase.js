/**
 * Medal Showcase Modal
 *
 * Renders a full-size country canvas with absolutely-positioned medal
 * images and a glass overlay on top.
 *
 * Coordinate data is loaded from the API (/api/campaign/<name>/showcase)
 * which in turn parses IL-2_Tracker_award_coordinates.xlsx.
 *
 * Developer notes
 * ---------------
 * – Canvas background is a plain <img>; medals and the overlay are <img>
 *   elements with absolute positioning inside a relative container.
 * – The container is sized to match the canvas image's natural pixel size
 *   (1 : 1 by default; a uniform scale factor can be applied if needed).
 * – The modal is closed by: the ×-button, pressing ESC, or clicking the
 *   backdrop behind the inner box.
 * – Replacement / variant selection is done server-side (medal_showcase.py);
 *   the JS only receives the already-resolved image_url for each slot.
 *
 * Replacement-chain logic (recap):
 *   Excel columns A (base) + G-K (higher variants).  The Python module
 *   walks from the highest variant down and picks the first one the pilot
 *   has earned.  The chosen image_url is what arrives in the JSON.
 *
 * USSR early / late:
 *   The server decides which canvas and which coordinate set to use
 *   (ussr_early vs ussr_late) based on the last mission date.  The JS
 *   simply renders whatever the server returns.
 */

/* global i18n, API */

const MedalShowcaseModal = (() => {
    // ------------------------------------------------------------------ //
    //  Private state
    // ------------------------------------------------------------------ //
    let _overlay        = null;   // backdrop div
    let _canvasImg      = null;   // background canvas <img>
    let _medalContainer = null;   // relative-positioned layer for medals
    let _stage          = null;   // stage div – the CSS transform target
    let _scaler         = null;   // wrapper sized to post-scale visual dimensions
    let _closeBtn       = null;
    let _isOpen         = false;
    let _currentData    = null;
    let _nativeW        = 0;      // natural canvas width in px
    let _nativeH        = 0;      // natural canvas height in px
    let _resizeTimer    = null;   // debounce handle for window resize

    // ------------------------------------------------------------------ //
    //  Build DOM (once)
    // ------------------------------------------------------------------ //
    function _build() {
        if (_overlay) return;

        // ---- backdrop ----
        _overlay = document.createElement('div');
        _overlay.className = 'msc-backdrop';
        _overlay.setAttribute('aria-hidden', 'true');
        _overlay.setAttribute('role', 'dialog');
        _overlay.setAttribute('aria-modal', 'true');
        _overlay.setAttribute('aria-label',
            i18n && i18n.t ? i18n.t('ui.medal_showcase.title') : 'Medal Showcase');

        // ---- inner box ----
        const box = document.createElement('div');
        box.className = 'msc-box';

        // ---- close button ----
        _closeBtn = document.createElement('button');
        _closeBtn.type = 'button';
        _closeBtn.className = 'msc-close';
        _closeBtn.setAttribute('aria-label',
            i18n && i18n.t ? i18n.t('ui.button.close') : 'Close');
        _closeBtn.textContent = '×';
        _closeBtn.addEventListener('click', close);

        // ---- scaler wrapper – JS sets width/height to post-scale visual dims ----
        _scaler = document.createElement('div');
        _scaler.className = 'msc-scaler';

        // ---- canvas stage – the single transform target (bg + medals + overlay) ----
        _stage = document.createElement('div');
        _stage.className = 'msc-stage';

        // background canvas image
        _canvasImg = document.createElement('img');
        _canvasImg.className = 'msc-canvas';
        _canvasImg.alt = '';
        _canvasImg.draggable = false;
        _stage.appendChild(_canvasImg);

        // medal container (same size as canvas, absolute positioned over it)
        _medalContainer = document.createElement('div');
        _medalContainer.className = 'msc-medals';
        _stage.appendChild(_medalContainer);

        _scaler.appendChild(_stage);
        box.appendChild(_closeBtn);
        box.appendChild(_scaler);
        _overlay.appendChild(box);
        document.body.appendChild(_overlay);

        // ---- event handlers ----
        _overlay.addEventListener('click', (e) => {
            if (e.target === _overlay) close();
        });

        document.addEventListener('keydown', (e) => {
            if (_isOpen && e.key === 'Escape') {
                e.preventDefault();
                e.stopPropagation();
                close();
            }
        }, true);

        // Recompute scale whenever the browser window is resized.
        window.addEventListener('resize', _onResize);
    }

    // ------------------------------------------------------------------ //
    //  Viewport-adaptive scaling
    // ------------------------------------------------------------------ //

    /**
     * Compute a uniform scale factor so the showcase fits within 90% of the
     * current viewport in both dimensions.
     *   scale = min(1, 0.9·vw / nativeW, 0.9·vh / nativeH)
     * The min(1, …) ensures we never upscale – only downscale when needed.
     */
    function _computeScale() {
        if (!_nativeW || !_nativeH) return 1;
        return Math.min(
            1,
            (0.9 * window.innerWidth)  / _nativeW,
            (0.9 * window.innerHeight) / _nativeH
        );
    }

    /**
     * Apply a CSS transform to the entire stage and resize the scaler wrapper
     * to match the post-transform visual dimensions.
     *
     * Scaling a single wrapper element (background + medals + overlay together)
     * means all absolute coordinates remain correct without any recalculation.
     * Using transform-origin: top left lets the scaler be sized as nativeW*s ×
     * nativeH*s, which tells the flex-centered backdrop the correct bounds.
     */
    function _applyScale() {
        if (!_stage || !_scaler || !_nativeW || !_nativeH) return;
        const s = _computeScale();
        _stage.style.transform       = `scale(${s})`;
        _stage.style.transformOrigin = 'top left';
        // Shrink the wrapper to the visible (post-transform) size so the
        // flex-centered backdrop calculates the right centering offset.
        _scaler.style.width  = `${Math.round(_nativeW * s)}px`;
        _scaler.style.height = `${Math.round(_nativeH * s)}px`;
    }

    /** Debounced resize handler – recomputes scale while the modal is open. */
    function _onResize() {
        if (!_isOpen) return;
        clearTimeout(_resizeTimer);
        _resizeTimer = setTimeout(_applyScale, 60);
    }

    // ------------------------------------------------------------------ //
    //  Render helpers
    // ------------------------------------------------------------------ //

    /**
     * Place a single medal image absolutely inside _medalContainer.
     *
     * Each _big1.png is a padded image: the medal content sits inside a larger
     * transparent canvas (e.g. 512×512).  `imgW/imgH` are the natural PNG
     * dimensions; `imgX/imgY` are the pixel offset where the content starts.
     * We use CSS background-image to crop out exactly the content region, so
     * the medal fills its coordinate slot without letterboxing.
     *
     * @param {string} imageUrl
     * @param {number} x, y     - top-left of the slot on the canvas
     * @param {number} w, h     - slot dimensions on the canvas
     * @param {string} name
     * @param {number} imgW, imgH - natural PNG dimensions (0 = unknown)
     * @param {number} imgX, imgY - content offset within the PNG (0 = full image)
     * @returns {HTMLElement}
     */
    function _placeMedal(imageUrl, x, y, w, h, name, imgW, imgH, imgX, imgY) {
        const el = document.createElement('div');
        el.className = 'msc-medal';
        el.dataset.name = name || '';
        el.title = name || '';

        // All coordinates stay in native canvas pixels.  Downscaling is handled
        // by a single CSS transform on the parent stage, so no per-element
        // multiplication is needed here.
        el.style.left   = `${x}px`;
        el.style.top    = `${y}px`;
        el.style.width  = `${w}px`;
        el.style.height = `${h}px`;

        if (imgW && imgH) {
            // Use background-image: display the full PNG at its natural size
            // and shift it so the content area aligns with the slot.
            el.style.backgroundImage    = `url('${imageUrl}')`;
            el.style.backgroundSize     = `${imgW}px ${imgH}px`;
            el.style.backgroundPosition = `-${imgX || 0}px -${imgY || 0}px`;
            el.style.backgroundRepeat   = 'no-repeat';
        } else {
            // Fallback: scale image to fill slot (object-fit: contain equivalent)
            el.style.backgroundImage    = `url('${imageUrl}')`;
            el.style.backgroundSize     = 'contain';
            el.style.backgroundPosition = 'center';
            el.style.backgroundRepeat   = 'no-repeat';
        }

        // Dev aid: detect broken images
        const testImg = new Image();
        testImg.onerror = () => {
            console.warn('[MedalShowcase] Image failed to load:', imageUrl,
                         '(medal:', name, ')');
            el.style.outline = '2px dashed red';
        };
        testImg.src = imageUrl;

        return el;
    }

    /**
     * Render overlay image on top of all medals.
     * The overlay uses the same coordinate system as medals.
     */
    function _placeOverlay(overlayData) {
        if (!overlayData || !overlayData.url) return;
        const img = document.createElement('img');
        img.className = 'msc-overlay-img';
        img.src = overlayData.url;
        img.alt = '';
        img.draggable = false;

        img.style.left   = `${overlayData.x}px`;
        img.style.top    = `${overlayData.y}px`;
        img.style.width  = `${overlayData.w}px`;
        img.style.height = `${overlayData.h}px`;

        img.addEventListener('error', () => {
            console.warn('[MedalShowcase] Overlay image failed to load:', overlayData.url);
        });

        _medalContainer.appendChild(img);
    }

    /**
     * Set the stage to native canvas pixel dimensions once the image has loaded,
     * then compute and apply the CSS transform scale for the current viewport.
     */
    function _applyCanvasSize(naturalW, naturalH) {
        // Store native dimensions so _applyScale() (and _onResize) can recompute
        // the scale factor at any time without re-reading the DOM.
        _nativeW = naturalW;
        _nativeH = naturalH;
        _canvasImg.style.width       = `${naturalW}px`;
        _canvasImg.style.height      = `${naturalH}px`;
        _medalContainer.style.width  = `${naturalW}px`;
        _medalContainer.style.height = `${naturalH}px`;
        _applyScale();
    }

    // ------------------------------------------------------------------ //
    //  Public API
    // ------------------------------------------------------------------ //

    /**
     * Open the showcase modal with pre-fetched data.
     *
     * @param {object} data  - response from /api/campaign/<name>/showcase
     *   {
     *     country_key: string,
     *     canvas_url:  string,
     *     overlay:     { url, x, y, w, h } | null,
     *     medals:      Array<{ image_url, x, y, w, h, name }>
     *   }
     */
    function open(data) {
        _build();

        if (!data || !data.canvas_url) {
            console.error('[MedalShowcase] Cannot open: missing data', data);
            return;
        }

        _currentData = data;

        // Reset native dimensions so _applyScale() doesn't use stale values
        // from a previously opened showcase with a different canvas size.
        _nativeW = 0;
        _nativeH = 0;

        // Clear previous content
        _medalContainer.innerHTML = '';
        _canvasImg.removeAttribute('style');

        // ---- Load background canvas ----
        _canvasImg.onload = () => {
            _applyCanvasSize(_canvasImg.naturalWidth, _canvasImg.naturalHeight);
        };
        _canvasImg.onerror = () => {
            console.error('[MedalShowcase] Canvas failed to load:', data.canvas_url);
        };
        _canvasImg.src = data.canvas_url;

        // ---- Place medal images ----
        const medals = Array.isArray(data.medals) ? data.medals : [];
        medals.forEach((medal) => {
            const el = _placeMedal(
                medal.image_url, medal.x, medal.y, medal.w, medal.h, medal.name,
                medal.img_w, medal.img_h, medal.img_x, medal.img_y
            );
            _medalContainer.appendChild(el);
        });

        // ---- Place overlay last (on top) ----
        _placeOverlay(data.overlay);

        // ---- Show modal ----
        _overlay.classList.add('is-open');
        _overlay.setAttribute('aria-hidden', 'false');
        document.body.classList.add('modal-open');
        _isOpen = true;

        // Focus the close button for keyboard navigation
        requestAnimationFrame(() => _closeBtn && _closeBtn.focus());
    }

    function close() {
        if (!_isOpen) return;
        _overlay.classList.remove('is-open');
        _overlay.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('modal-open');
        _isOpen = false;
        _currentData = null;
    }

    function isOpen() { return _isOpen; }

    return { open, close, isOpen };
})();


// ==========================================================================
//  Button factory + API fetch helper (used from detail.js)
// ==========================================================================

/**
 * Create and return the "Medal Showcase" button element.
 * Call addMedalShowcaseButton() to integrate it into the left column.
 */
function createMedalShowcaseButton() {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'medal-showcase-btn';
    btn.className = 'medal-showcase-btn';

    const label = (i18n && i18n.t)
        ? i18n.t('ui.medal_showcase.button')
        : 'Medal Showcase';
    btn.textContent = label;

    return btn;
}

/**
 * Fetch showcase data and open the modal.
 * Shows a brief loading state on the button itself.
 *
 * @param {string} campaignName
 * @param {HTMLButtonElement} btn
 */
async function openMedalShowcase(campaignName, btn) {
    if (!campaignName) return;

    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = (i18n && i18n.t)
        ? i18n.t('ui.medal_showcase.loading')
        : 'Loading…';

    try {
        const response = await fetch(`/api/campaign/${encodeURIComponent(campaignName)}/showcase`);

        if (!response.ok) {
            const body = await response.json().catch(() => ({}));
            console.warn('[MedalShowcase] API error:', response.status, body);

            // Show friendly message for unsupported country
            if (response.status === 404) {
                btn.textContent = (i18n && i18n.t)
                    ? i18n.t('ui.medal_showcase.not_available')
                    : 'Not available';
                btn.disabled = true;
                return;
            }

            const msg = body.error || `HTTP ${response.status}`;
            const detail = body.detail ? ` — ${body.detail}` : '';
            throw new Error(msg + detail);
        }

        const data = await response.json();
        MedalShowcaseModal.open(data);
    } catch (err) {
        console.error('[MedalShowcase] Failed to load showcase:', err);
        btn.textContent = (i18n && i18n.t)
            ? i18n.t('ui.medal_showcase.error')
            : 'Error loading';
        btn.title = err.message || '';   // visible on hover for quick diagnosis
        btn.disabled = true;
        return;
    } finally {
        // Restore button unless it was disabled by a non-recoverable state
        if (!btn.disabled || btn.textContent === originalText) {
            btn.disabled = false;
            btn.textContent = originalText;
        }
    }

    // Re-enable after modal closes (ESC / X)
    btn.disabled = false;
    btn.textContent = originalText;
}


/**
 * Fetch career showcase data and open the modal.
 * Mirror of openMedalShowcase() but calls the career endpoint.
 *
 * @param {string|number} careerId  root_career_id
 * @param {HTMLButtonElement} btn
 */
async function openCareerMedalShowcase(careerId, btn) {
    if (!careerId) return;

    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = (i18n && i18n.t)
        ? i18n.t('ui.medal_showcase.loading')
        : 'Loading\u2026';

    try {
        const response = await fetch(
            `/api/career/${encodeURIComponent(careerId)}/showcase`
        );

        if (!response.ok) {
            const body = await response.json().catch(() => ({}));
            console.warn('[MedalShowcase] Career API error:', response.status, body);

            if (response.status === 404) {
                btn.textContent = (i18n && i18n.t)
                    ? i18n.t('ui.medal_showcase.not_available')
                    : 'Not available';
                btn.disabled = true;
                return;
            }

            const msg = body.error || `HTTP ${response.status}`;
            const detail = body.detail ? ` \u2014 ${body.detail}` : '';
            throw new Error(msg + detail);
        }

        const data = await response.json();
        MedalShowcaseModal.open(data);
    } catch (err) {
        console.error('[MedalShowcase] Failed to load career showcase:', err);
        btn.textContent = (i18n && i18n.t)
            ? i18n.t('ui.medal_showcase.error')
            : 'Error loading';
        btn.title = err.message || '';
        btn.disabled = true;
        return;
    } finally {
        if (!btn.disabled || btn.textContent === originalText) {
            btn.disabled = false;
            btn.textContent = originalText;
        }
    }

    btn.disabled = false;
    btn.textContent = originalText;
}
