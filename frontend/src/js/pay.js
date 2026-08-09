/**
 * pay.js
 * Logic for the public Instapay submission form
 */

let selectedFile = null;

// Localised string helper — i18n.js exposes window.i18nT (Arabic by default).
function t(key, fallback) {
    return (typeof window.i18nT === 'function') ? window.i18nT(key, fallback) : (fallback || key);
}

// EGP plans for the Instapay flow. Keyed by the ?plan= cycle passed from the
// pricing page. Label/period are dictionary keys resolved at render time so the
// language toggle can re-render them.
//
// The AMOUNTS are read from src/js/pricing.js, which pay.html loads for this
// one reason: this file used to carry its own copy and was still quoting 4000
// for the yearly plan after it moved to 3500 — so a member sent here from the
// pricing page saw one number on the card and a different one on the transfer
// screen. The literals below are only a fallback for pricing.js failing to
// load, and are not the source of truth.
const PLAN_PRICES = {
    monthly: { amount: 600, labelKey: 'planMonthly', periodKey: 'periodMonthly' },
    quarterly: { amount: 1200, labelKey: 'planQuarterly', periodKey: 'periodQuarterly' },
    yearly: { amount: 3500, labelKey: 'planYearly', periodKey: 'periodYearly' },
};

Object.keys(PLAN_PRICES).forEach(key => {
    const shared = window.GhawyPricing
        && window.GhawyPricing.PLANS.EGP
        && window.GhawyPricing.PLANS.EGP[key];
    if (shared) PLAN_PRICES[key].amount = shared.amount;
});

// Resolve the selected plan from the URL (defaults to monthly).
const selectedPlanKey = (new URLSearchParams(location.search).get('plan') || 'monthly').toLowerCase();
const selectedPlan = PLAN_PRICES[selectedPlanKey] || null;

// An active member who came here on purpose to renew early (from /renewal)
// must be allowed to stay — otherwise the Instapay option is unreachable for
// anyone whose subscription hasn't lapsed yet.
const renewIntent = (new URLSearchParams(location.search).get('intent') || '') === 'renew';

const token = localStorage.getItem('token');

// The address the backend has on file for this member. Filled by the gate
// below and reused by the success screen, so what we promise to email is the
// address the request was actually filed under — never anything typed here.
let memberEmail = '';

// The last refusal, kept so a language toggle can redraw the panel (the date
// in it is formatted, not translated by the dictionary).
let blockedState = null;

if (!token) {
    localStorage.removeItem('user'); window.location.href = '/login';
} else {
    gateSubmission();
}

/**
 * Decide what this page shows before it shows anything.
 *
 * Two states mean there is nothing to upload: a request already under review,
 * and a subscription that has not run out. Previously the second one silently
 * bounced the member to the dashboard, which told them nothing, and the first
 * was not checked at all — you picked a file, waited, and got an English 409
 * in a red toast. Both now arrive as a panel that says which case it is.
 *
 * The single exception is an early renewal: /renewal sends an active member
 * here with intent=renew, and that has to reach the form. It is passed through
 * to the backend so both sides apply the same rule.
 */
async function gateSubmission() {
    try {
        const qs = renewIntent ? '?intent=renew' : '';
        const res = await fetch(`${API}/manual-payments/my-status${qs}`, {
            headers: { 'Authorization': `Bearer ${token}` },
        });

        // Any non-OK answer falls through to the catch and opens the form.
        // Deliberately including 401: the frontend is deployed from a bind
        // mount and the backend from an image, so this file can be live for a
        // while before /my-status exists — and this API answers 401, not 404,
        // for a path it does not know. Signing members out of /pay because the
        // backend has not caught up yet would be a far worse failure than
        // showing a form the server will still refuse.
        if (!res.ok) throw new Error(`my-status ${res.status}`);

        const state = await res.json();
        memberEmail = (state.email || '').trim();

        if (state.can_submit) {
            showFormView();
            return;
        }
        renderBlocked(state);
    } catch (err) {
        // Fail open. /submit enforces the same two rules server-side, so the
        // cost of guessing wrong here is one wasted upload; failing closed
        // would lock out every member whose network blinked.
        console.error('Could not check submission eligibility:', err);
        showFormView();
    }
}

function showFormView() {
    const form = document.getElementById('pay-form-view');
    if (form) form.style.display = '';
}

/**
 * Draw the refusal. One card, two reasons — the wording, the icon and which
 * rows appear are all driven off `state.reason`.
 */
function renderBlocked(state) {
    blockedState = state;
    const view = document.getElementById('pay-blocked-view');
    if (!view) return;

    const pending = state.reason === 'pending';

    setKey('blocked-title', pending ? 'payBlockedPendingTitle' : 'payBlockedActiveTitle');
    setKey('blocked-desc', pending ? 'payBlockedPendingDesc' : 'payBlockedActiveDesc');

    // Waiting on a review is not success, so it does not get the green tick.
    const wrap = document.getElementById('blocked-icon-wrap');
    const icon = document.getElementById('blocked-icon');
    wrap.classList.toggle('is-waiting', pending);
    icon.setAttribute('data-lucide', pending ? 'clock' : 'check-circle');

    // ── pending: request number, what happens next, how to chase us ──
    const ref = document.getElementById('blocked-ref-row');
    ref.hidden = !(pending && state.request_ref);
    if (state.request_ref) document.getElementById('blocked-ref').textContent = state.request_ref;

    document.getElementById('blocked-window').hidden = !pending;
    document.getElementById('blocked-support').hidden = !pending;

    const emailRow = document.getElementById('blocked-email-row');
    emailRow.hidden = !pending;
    if (pending) {
        setEmailLine('blocked-email-lead', 'blocked-email', 'payBlockedEmailNote', 'payBlockedEmailPlain');
    }

    // ── still subscribed: until when, and the two ways out ──
    const until = formatDate(state.end_at);
    const untilRow = document.getElementById('blocked-until-row');
    untilRow.hidden = pending || !until;
    if (until) document.getElementById('blocked-until').textContent = until;

    document.getElementById('blocked-dashboard-btn').hidden = pending;
    document.getElementById('blocked-renew-row').hidden = pending;

    // An active member with no recorded expiry would otherwise get an empty
    // grey box.
    const details = document.getElementById('blocked-details');
    details.hidden = !pending && untilRow.hidden;

    view.style.display = 'block';
    if (window.lucide) window.lucide.createIcons();
}

/**
 * Point an element at a different dictionary key and redraw it now, so a later
 * language toggle keeps whichever wording ended up on screen.
 */
function setKey(id, key) {
    const el = document.getElementById(id);
    if (!el) return;
    el.setAttribute('data-i18n', key);
    el.textContent = t(key);
}

/**
 * "…we'll email you at: address" when we have one, and the plain full-stop
 * sentence when we do not — never a dangling colon or the word "undefined".
 */
function setEmailLine(leadId, emailId, withKey, plainKey) {
    const span = document.getElementById(emailId);
    if (!span) return;

    if (memberEmail) {
        setKey(leadId, withKey);
        span.textContent = memberEmail;
        span.hidden = false;
    } else {
        setKey(leadId, plainKey);
        span.textContent = '';
        span.hidden = true;
    }
}

/**
 * A backend ISO timestamp as a date the member can read, in their language.
 *
 * Formatted in Africa/Cairo, not in the viewer's zone. A subscription expiry
 * is a Cairo date — the backend sends it as Cairo-local with an offset — and
 * formatting it locally makes a midnight expiry render as the previous day for
 * anyone reading from further west.
 */
function formatDate(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return '';
    const locale = (document.documentElement.lang === 'en') ? 'en-GB' : 'ar-EG';
    try {
        return new Intl.DateTimeFormat(locale, {
            year: 'numeric', month: 'long', day: 'numeric', timeZone: 'Africa/Cairo',
        }).format(d);
    } catch (e) {
        return String(iso).slice(0, 10);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Normalise the hardcoded fallback in the markup through the same path the
    // backend value takes, so `data-full` is populated even when the config
    // request fails and the copy button still copies a working link.
    const insta = document.getElementById('display-instapay');
    if (insta) setInstapayDisplay(insta.textContent.trim());
    loadPaymentConfig();
    setupDragAndDrop();
});

// Load config from backend
async function loadPaymentConfig() {
    try {
        const res = await fetch(`${API}/config/payment-info`);
        if (!res.ok) throw new Error("Failed to load config");
        const config = await res.json();

        // Only override the hardcoded link if the backend has a real value configured
        // (default placeholder "xxxx" / empty would otherwise hide the payment link).
        const instapay = config.instapay_number;
        if (instapay && instapay !== "xxxx") {
            setInstapayDisplay(instapay);
            // If it's a full payment URL, point the "Pay now" button to it too.
            if (/^https?:\/\//i.test(instapay)) {
                document.getElementById('pi-instapay-link').href = instapay;
            }
        }
        // Price/period follow the chosen plan; fall back to the backend default (monthly).
        if (selectedPlan) {
            document.getElementById('display-price').innerText = selectedPlan.amount;
            renderPlanLabels();
        } else {
            document.getElementById('display-price').innerText = config.subscription_price;
        }
    } catch (error) {
        console.error("Error loading payment config:", error);
        showToast(t('payErrLoadConfig'), "error");
    }
}

// Plan name + billing period are written by JS, so re-render them on toggle.
function renderPlanLabels() {
    if (!selectedPlan) return;
    const period = document.getElementById('display-period');
    const plan = document.getElementById('display-plan');
    if (period) period.innerText = t(selectedPlan.periodKey);
    if (plan) plan.innerText = `• ${t(selectedPlan.labelKey)}`;
}

document.addEventListener('languagechange', renderPlanLabels);

// The blocked panel carries a date, which the dictionary cannot translate, so
// it has to be re-formatted rather than just re-keyed.
document.addEventListener('languagechange', () => {
    if (blockedState) renderBlocked(blockedState);
});

// Copy to clipboard
/**
 * Put the Instapay handle on screen without letting it wrap.
 *
 * The raw value is a full URL — "https://ipn.eg/S/salahabouzeid2/instapay/
 * 8D6xNU" — and at the width of that box it broke across two lines, mid-word,
 * which is what the client saw and disliked. Two things fix it and neither
 * loses information:
 *
 *   - the scheme is dropped from the DISPLAY. "https://" is eight characters
 *     that tell a payer nothing.
 *   - `data-full` keeps the real value, and it is what the copy button and
 *     the title tooltip use. So what gets copied is always the complete,
 *     working link no matter how the label is shortened or ellipsised by CSS.
 */
function setInstapayDisplay(value) {
    const el = document.getElementById('display-instapay');
    if (!el || !value) return;
    el.dataset.full = value;
    el.title = value;
    el.textContent = String(value).replace(/^https?:\/\//i, '');
}

function copyInstapay() {
    const el = document.getElementById('display-instapay');
    // Always the full value, never the shortened label on screen.
    const text = (el.dataset.full || el.innerText || '').trim();
    if (!text || text === "---") return;

    navigator.clipboard.writeText(text).then(() => {
        showToast(t('payCopiedToast'), 'success');
        const btn = document.getElementById('copy-instapay-btn');
        const originalHtml = btn.innerHTML;
        btn.innerHTML = `<i data-lucide="check"></i> ${t('payCopied')}`;
        window.lucide && window.lucide.createIcons();
        setTimeout(() => {
            btn.innerHTML = originalHtml;
            window.lucide && window.lucide.createIcons();
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy: ', err);
        showToast(t('payCopyFailed'), 'error');
    });
}

// Drag & Drop Setup
function setupDragAndDrop() {
    const dropArea = document.getElementById('file-drop-area');
    const fileInput = document.getElementById('pay-receipt');

    // Prevent default behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Highlight area
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, () => dropArea.classList.add('drag-over'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, () => dropArea.classList.remove('drag-over'), false);
    });

    // Handle dropped files
    dropArea.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFile(files[0]);
            // Sync with input
            fileInput.files = files;
        }
    });

    // Handle selected files
    fileInput.addEventListener('change', function () {
        if (this.files && this.files.length > 0) {
            handleFile(this.files[0]);
        }
    });
}

// The object URL of whatever is on screen, so it can be released before the
// next one replaces it. Without this every "change image" leaks the previous
// file for as long as the tab is open.
let previewURL = null;

function handleFile(file) {
    const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
    if (!validTypes.includes(file.type)) {
        showToast(t('payErrFileType'), 'error');
        return;
    }

    // 5MB limit
    if (file.size > 5 * 1024 * 1024) {
        showToast(t('payErrFileSize'), 'error');
        return;
    }

    selectedFile = file;
    renderPreview(file);
}

/**
 * Show what was actually uploaded.
 *
 * The old preview was a generic icon, the file name and a red ✕, sitting on
 * top of the drop zone. People read the ✕ as an error and thought the upload
 * had failed — so this shows the receipt itself, says "تم رفع الصورة" under
 * it, and the only button says "تغيير الصورة".
 *
 * A PDF is an accepted upload and cannot be drawn, so it gets a file card and
 * the wording switches from "الصورة" to "الملف" — telling someone who uploaded
 * a PDF that their image is ready is a small lie that costs trust at exactly
 * the wrong moment.
 */
function renderPreview(file) {
    const isPDF = file.type === 'application/pdf';
    const media = document.getElementById('file-preview-media');
    const preview = document.getElementById('file-preview');
    const dropArea = document.getElementById('file-drop-area');

    if (previewURL) URL.revokeObjectURL(previewURL);
    previewURL = null;

    if (isPDF) {
        media.innerHTML = '<div class="file-preview-doc"><i data-lucide="file-text"></i></div>';
    } else {
        previewURL = URL.createObjectURL(file);
        const img = document.createElement('img');
        img.className = 'file-preview-img';
        img.alt = '';
        img.src = previewURL;
        media.innerHTML = '';
        media.appendChild(img);
    }

    document.getElementById('file-name-display').innerText = file.name;

    const label = document.getElementById('file-preview-label');
    const changeLabel = document.getElementById('file-change-label');
    // Point the data-i18n key at the right wording too, so a language switch
    // after the upload keeps saying "file" for a PDF and "image" for an image.
    label.setAttribute('data-i18n', isPDF ? 'payUploadedFile' : 'payUploaded');
    label.innerText = t(isPDF ? 'payUploadedFile' : 'payUploaded');
    changeLabel.setAttribute('data-i18n', isPDF ? 'payChangeFile' : 'payChangeImage');
    changeLabel.innerText = t(isPDF ? 'payChangeFile' : 'payChangeImage');

    dropArea.hidden = true;
    preview.hidden = false;

    // The check-circle and refresh icons are <i data-lucide> placeholders until
    // this runs; the file card's icon is brand new markup every time.
    if (window.lucide) window.lucide.createIcons();
}

/** The button under the preview: reopen the picker, keep the current file. */
function changeFile() {
    document.getElementById('pay-receipt').click();
}

// Submit Form
async function submitPayment() {
    const amount = document.getElementById('display-price').innerText;

    if (!selectedFile) {
        showToast(t('payErrNoReceipt'), 'error');
        return;
    }

    const submitBtn = document.getElementById('pay-submit-btn');
    const spinner = document.getElementById('btn-spinner');

    submitBtn.disabled = true;
    spinner.style.display = 'block';

    const formData = new FormData();

    const parsedAmount = parseFloat(amount);
    if (!isNaN(parsedAmount)) {
        formData.append('amount', parsedAmount);
    }

    // Send the chosen plan so approval grants the matching subscription length.
    if (selectedPlan) {
        formData.append('plan', selectedPlanKey);
    }

    // Deliberate early renewal — tells the backend not to apply the "you are
    // still subscribed" rule to a member who came here precisely because they
    // are still subscribed and want to extend.
    if (renewIntent) {
        formData.append('intent', 'renew');
    }

    formData.append('receipt', selectedFile);

    try {
        const res = await fetch(`${API}/manual-payments/submit`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData // FormData sets correct multipart header automatically
        });

        const data = await res.json();

        if (!res.ok) {
            // 409 means the gate above and the backend disagreed — a second
            // tab got there first, or the subscription was approved while this
            // page sat open. Show the reason as a panel rather than flashing
            // the backend's sentence in a red toast.
            if (res.status === 409) {
                document.getElementById('pay-form-view').style.display = 'none';
                submitBtn.disabled = false;
                spinner.style.display = 'none';
                await gateSubmission();
                return;
            }
            throw new Error(data.detail || t('payErrSubmit'));
        }

        // Show success screen
        document.getElementById('pay-form-view').style.display = 'none';
        document.getElementById('pay-success-view').style.display = 'block';

        document.getElementById('success-ref').innerText = `MANUAL-${data.id}`;

        // The address the request was actually filed under. Prefer what the
        // backend just echoed back over what the gate read earlier.
        if (data.email) memberEmail = String(data.email).trim();
        setEmailLine('success-desc', 'success-email', 'paySuccessDescEmail', 'paySuccessDesc');

    } catch (error) {
        console.error("Submit error:", error);
        showToast(error.message, "error");
        submitBtn.disabled = false;
        spinner.style.display = 'none';
    }
}

function showToast(message, type) {
    const toast = document.createElement('div');
    toast.className = `toast ${type || 'success'}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}
