/**
 * pay.js
 * Logic for the public Instapay submission form
 */

let selectedFile = null;

// EGP plans for the Instapay flow. Keyed by the ?plan= cycle passed from the pricing page.
const PLAN_PRICES = {
    monthly: { amount: 600, label: 'Monthly', period: '/ month' },
    quarterly: { amount: 1200, label: '3 Months', period: '/ 3 months' },
    yearly: { amount: 4000, label: 'Yearly', period: '/ year' },
};

// Resolve the selected plan from the URL (defaults to monthly).
const selectedPlanKey = (new URLSearchParams(location.search).get('plan') || 'monthly').toLowerCase();
const selectedPlan = PLAN_PRICES[selectedPlanKey] || null;

const token = localStorage.getItem('token');
if (!token) {
    localStorage.removeItem('user'); window.location.href = '/login';
} else {
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
            document.getElementById('display-period').innerText = selectedPlan.period;
            document.getElementById('display-plan').innerText = `• ${selectedPlan.label}`;
        } else {
            document.getElementById('display-price').innerText = config.subscription_price;
        }
    } catch (error) {
        console.error("Error loading payment config:", error);
        showToast("Error loading payment information", "error");
    }
}

// Copy to clipboard
function copyInstapay() {
    const text = document.getElementById('display-instapay').innerText;
    if (text === "---") return;

    navigator.clipboard.writeText(text).then(() => {
        showToast("Instapay number copied!", "success");
        const btn = document.getElementById('copy-instapay-btn');
        const originalHtml = btn.innerHTML;
        btn.innerHTML = `<i data-lucide="check"></i> Copied`;
        lucide.createIcons();
        setTimeout(() => {
            btn.innerHTML = originalHtml;
            lucide.createIcons();
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy: ', err);
        showToast("Failed to copy text", "error");
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

function handleFile(file) {
    const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
    if (!validTypes.includes(file.type)) {
        showToast("Invalid file type. Please upload a JPG, PNG, WebP, or PDF.", "error");
        return;
    }

    // 5MB limit
    if (file.size > 5 * 1024 * 1024) {
        showToast("File too large. Maximum size is 5MB.", "error");
        return;
    }

    selectedFile = file;
    document.getElementById('file-name-display').innerText = file.name;
    document.getElementById('file-preview').style.display = 'flex';
}

function removeFile() {
    selectedFile = null;
    document.getElementById('pay-receipt').value = '';
    document.getElementById('file-preview').style.display = 'none';
}

// Submit Form
async function submitPayment() {
    const amount = document.getElementById('display-price').innerText;

    if (!selectedFile) {
        showToast("Please upload your receipt screenshot", "error");
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
            throw new Error(data.detail || "Failed to submit request");
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
