/* ═══════════════════════════════════════════
   Voice Recorder Module — MediaRecorder API
═══════════════════════════════════════════ */

const RecorderModule = (function () {
    let mediaRecorder = null;
    let audioChunks = [];
    let recordingStartTime = null;
    let timerInterval = null;

    function init() {
        const recordBtn = document.getElementById('voiceRecordBtn');
        const recordingBar = document.getElementById('voiceRecordingBar');
        const cancelBtn = document.getElementById('recCancelBtn');
        const sendBtn = document.getElementById('recSendBtn');
        const timerEl = document.getElementById('recordingTimer');

        recordBtn.addEventListener('click', startRecording);
        cancelBtn.addEventListener('click', cancelRecording);
        sendBtn.addEventListener('click', stopAndSend);
    }

    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioChunks = [];
            mediaRecorder = new MediaRecorder(stream, { mimeType: getSupportedMimeType() });

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) audioChunks.push(e.data);
            };

            mediaRecorder.start();
            recordingStartTime = Date.now();

            // Show recording UI
            document.getElementById('voiceRecordingBar').style.display = 'flex';
            document.querySelector('.chat-input-row').style.display = 'none';

            // Start timer
            timerInterval = setInterval(updateTimer, 1000);
        } catch (err) {
            console.error('Mic access denied', err);
            showToast('Please allow microphone access', 'error');
        }
    }

    function updateTimer() {
        const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
        const mins = Math.floor(elapsed / 60);
        const secs = elapsed % 60;
        document.getElementById('recordingTimer').textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    function cancelRecording() {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(t => t.stop());
        }
        cleanup();
    }

    function stopAndSend() {
        if (!mediaRecorder || mediaRecorder.state === 'inactive') return;

        mediaRecorder.onstop = async () => {
            const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
            const ext = mediaRecorder.mimeType.includes('webm') ? 'webm' : 'ogg';
            const file = new File([blob], `voice_${Date.now()}.${ext}`, { type: mediaRecorder.mimeType });

            mediaRecorder.stream.getTracks().forEach(t => t.stop());
            cleanup();

            // Upload via chat module
            await ChatModule.uploadAndSend(file);
        };

        mediaRecorder.stop();
    }

    function cleanup() {
        clearInterval(timerInterval);
        document.getElementById('voiceRecordingBar').style.display = 'none';
        document.querySelector('.chat-input-row').style.display = 'flex';
        document.getElementById('recordingTimer').textContent = '0:00';
        audioChunks = [];
        mediaRecorder = null;
    }

    function getSupportedMimeType() {
        const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
        for (const type of types) {
            if (MediaRecorder.isTypeSupported(type)) return type;
        }
        return 'audio/webm';
    }

    return { init };
})();


