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
    let _closeBtn       = null;
    let _isOpen         = false;
    let _currentData    = null;

    // Scale factor: 1.0 = natural image pixels.
    // Increase if the canvas is very large and doesn't fit the viewport.
    const SCALE = 1.0;

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

        // ---- scrollable wrapper (in case canvas is very large) ----
        const scroller = document.createElement('div');
        scroller.className = 'msc-scroller';

        // ---- canvas stage (relative container) ----
        const stage = document.createElement('div');
        stage.className = 'msc-stage';

        // background canvas image
        _canvasImg = document.createElement('img');
        _canvasImg.className = 'msc-canvas';
        _canvasImg.alt = '';
        _canvasImg.draggable = false;
        stage.appendChild(_canvasImg);

        // medal container (same size as canvas, absolute positioned over it)
        _medalContainer = document.createElement('div');
        _medalContainer.className = 'msc-medals';
        stage.appendChild(_medalContainer);

        scroller.appendChild(stage);
        box.appendChild(_closeBtn);
        box.appendChild(scroller);
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
    }

    // ------------------------------------------------------------------ //
    //  Render helpers
    // ------------------------------------------------------------------ //

    /**
     * Place a single medal image absolutely inside _medalContainer.
     * @param {string} imageUrl
     * @param {number} x  - top-left x from Excel (natural pixels)
     * @param {number} y  - top-left y from Excel (natural pixels)
     * @param {number} w  - width from Excel (natural pixels)
     * @param {number} h  - height from Excel (natural pixels)
     * @param {string} name - showcase name for alt text / data attribute
     * @returns {HTMLImageElement}
     */
    function _placeMedal(imageUrl, x, y, w, h, name) {
        const img = document.createElement('img');
        img.className = 'msc-medal';
        img.src = imageUrl;
        img.alt = name || '';
        img.draggable = false;
        img.dataset.name = name || '';

        img.style.left   = `${Math.round(x * SCALE)}px`;
        img.style.top    = `${Math.round(y * SCALE)}px`;
        img.style.width  = `${Math.round(w * SCALE)}px`;
        img.style.height = `${Math.round(h * SCALE)}px`;

        // Log missing images (dev aid)
        img.addEventListener('error', () => {
            console.warn('[MedalShowcase] Image failed to load:', imageUrl,
                         '(medal:', name, ')');
            img.style.outline = '2px dashed red';
        });

        return img;
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

        img.style.left   = `${Math.round(overlayData.x * SCALE)}px`;
        img.style.top    = `${Math.round(overlayData.y * SCALE)}px`;
        img.style.width  = `${Math.round(overlayData.w * SCALE)}px`;
        img.style.height = `${Math.round(overlayData.h * SCALE)}px`;

        img.addEventListener('error', () => {
            console.warn('[MedalShowcase] Overlay image failed to load:', overlayData.url);
        });

        _medalContainer.appendChild(img);
    }

    /**
     * Resize _medalContainer and _canvasImg stage once the canvas has loaded.
     */
    function _applyCanvasSize(naturalW, naturalH) {
        const w = Math.round(naturalW * SCALE);
        const h = Math.round(naturalH * SCALE);
        _canvasImg.style.width  = `${w}px`;
        _canvasImg.style.height = `${h}px`;
        _medalContainer.style.width  = `${w}px`;
        _medalContainer.style.height = `${h}px`;
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
            const img = _placeMedal(
                medal.image_url, medal.x, medal.y, medal.w, medal.h, medal.name
            );
            _medalContainer.appendChild(img);
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

            throw new Error(body.error || `HTTP ${response.status}`);
        }

        const data = await response.json();
        MedalShowcaseModal.open(data);
    } catch (err) {
        console.error('[MedalShowcase] Failed to load showcase:', err);
        btn.textContent = (i18n && i18n.t)
            ? i18n.t('ui.medal_showcase.error')
            : 'Error loading';
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
