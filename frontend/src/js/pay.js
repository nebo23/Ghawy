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
if (!token) {
    localStorage.removeItem('user'); window.location.href = '/login';
} else if (!renewIntent) {
    // If user is already active, redirect them away from the payment screen
    fetch(`${API}/profile/me?_t=`, {
        headers: { 'Authorization': `Bearer ${token}` }
    })
        .then(res => {
            if (res.ok) return res.json();
        })
        .then(user => {
            if (user && user.is_active) {
                window.location.href = user.onboarding_completed ? 'dashboard.html' : 'onboarding.html';
            }
        })
        .catch(() => { });
}

document.addEventListener('DOMContentLoaded', () => {
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
            document.getElementById('display-instapay').innerText = instapay;
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

// Copy to clipboard
function copyInstapay() {
    const text = document.getElementById('display-instapay').innerText;
    if (text === "---") return;

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
            throw new Error(data.detail || t('payErrSubmit'));
        }

        // Show success screen
        document.getElementById('pay-form-view').style.display = 'none';
        document.getElementById('pay-success-view').style.display = 'block';

        document.getElementById('success-ref').innerText = `MANUAL-${data.id}`;

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
