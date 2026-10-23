package dev.careerground.interview

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.speech.RecognitionListener
import android.speech.RecognitionSupport
import android.speech.RecognitionSupportCallback
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import java.util.Locale

/** On-device only; no cloud fallback, model download, audio files or transcript logs. */
class DeviceVoice(private val context: Context, private val changed: () -> Unit,
                  private val transcript: (String, Boolean) -> Unit) {
    var status = "한국어 기기 내 음성 준비 상태를 확인해 주세요."; private set
    var ready = false; private set
    val listening: Boolean get() = capture.active
    var localTtsReady = false; private set
    private var recognizer: SpeechRecognizer? = null
    private val handler = Handler(Looper.getMainLooper())
    private val capture = VoiceCaptureWindow()
    private val draft = VoiceTranscript()
    private var emptyAttempts = 0
    private var attempts = 0
    private var segmented = true
    private var generation = 0
    private var disposed = false
    private var tts: TextToSpeech? = null
    private fun notifyState(value: String) { status = value; changed() }
    private fun intent(segments: Boolean = false) = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ko-KR")
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        if (segments) {
            putExtra(RecognizerIntent.EXTRA_SEGMENTED_SESSION,
                RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 4000)
        }
    }

    init {
        tts = TextToSpeech(context) { code ->
            if (!disposed && code == TextToSpeech.SUCCESS) {
                val local = tts?.voices?.firstOrNull { it.locale.language == "ko" &&
                    !it.isNetworkConnectionRequired &&
                    !it.features.orEmpty().contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED) }
                localTtsReady = local != null && tts?.setVoice(local) == TextToSpeech.SUCCESS
                changed()
            }
        }
    }

    fun check() {
        if (disposed || listening) return
        generation++
        val expected = generation
        ready = false
        if (!SpeechRecognizer.isOnDeviceRecognitionAvailable(context)) {
            notifyState("기기 내 음성 인식 미지원 · 텍스트로 진행할 수 있습니다."); return
        }
        recognizer?.destroy()
        val service = SpeechRecognizer.createOnDeviceSpeechRecognizer(context)
        recognizer = service
        service.setRecognitionListener(listener(-1))
        notifyState("한국어 설치 상태 확인 중 · 다운로드하지 않습니다.")
        handler.postDelayed({
            if (!disposed && expected == generation && !ready) {
                generation++; notifyState("음성 지원 조회 시간 초과 · 텍스트로 진행해 주세요.")
            }
        }, 10000)
        try {
            service.checkRecognitionSupport(intent(), context.mainExecutor, object : RecognitionSupportCallback {
                override fun onSupportResult(result: RecognitionSupport) {
                    if (disposed || expected != generation) return
                    val installed = result.installedOnDeviceLanguages.any { Locale.forLanguageTag(it).language == "ko" }
                    ready = installed && result.onlineLanguages.isEmpty()
                    if (ready) notifyState("한국어 기기 내 인식 준비됨 · 마이크 사용 후 초안 확인이 필요합니다.")
                    else if (result.supportedOnDeviceLanguages.any { Locale.forLanguageTag(it).language == "ko" } ||
                        result.pendingOnDeviceLanguages.any { Locale.forLanguageTag(it).language == "ko" }) {
                        notifyState("한국어 모델 설치 필요 · 다운로드는 승인 후 별도 진행 · 텍스트 대안 가능")
                    } else notifyState("한국어 기기 내 인식을 확인할 수 없음 · 텍스트 대안 가능")
                }
                override fun onError(error: Int) {
                    if (!disposed && expected == generation) notifyState("음성 지원 조회 실패 [$error] · 텍스트 대안 가능")
                }
            })
        } catch (_: Exception) { notifyState("음성 지원 조회 오류 · 텍스트 대안 가능") }
    }

    fun start() {
        if (!ready || listening || disposed) return
        if (context.checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            notifyState("마이크 권한 없음 · 텍스트 대안 가능"); return
        }
        tts?.stop()
        draft.clear(); emptyAttempts = 0; attempts = 0; segmented = true
        val session = capture.begin(SystemClock.elapsedRealtime())
        startAttempt()
        handler.postDelayed({
            if (!disposed && capture.session == session && listening) stop()
        }, 120000)
    }

    private fun publish() { if (draft.text.isNotBlank()) transcript(draft.text, false) }
    private fun finishCapture(message: String = "전사 초안 · 숫자·기간·역할·동료 기여를 확인·수정 후 제출해 주세요.") {
        draft.preservePartial(); publish()
        capture.cancel()
        recognizer?.cancel()
        notifyState(message)
    }
    private fun startAttempt() {
        if (disposed || !capture.canContinue(SystemClock.elapsedRealtime())) return
        if (++attempts > 32) {
            finishCapture("음성 구간 한도 도달 · 남은 초안 확인 또는 텍스트로 계속해 주세요."); return
        }
        val token = capture.nextAttempt(SystemClock.elapsedRealtime()) ?: return
        draft.beginAttempt()
        recognizer?.setRecognitionListener(listener(token))
        notifyState("기기 내 연속 음성 인식 중 · 인식 마치기까지 이어 듣습니다 · 최대 120초 · 자동 제출 없음")
        try { recognizer?.startListening(intent(segmented)) }
        catch (_: Exception) { finishCapture("음성 시작 실패 · 남은 초안 확인 또는 텍스트 대안 가능") }
    }
    private fun terminal(token: Long, error: Int? = null) {
        val next = capture.terminal(token, SystemClock.elapsedRealtime())
        if (next == VoiceCaptureWindow.Next.IGNORE) return
        draft.preservePartial(); publish()
        if (next == VoiceCaptureWindow.Next.FINISH || draft.full) { finishCapture(); return }
        val unsupported = error == SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED ||
            error == SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE ||
            error == SpeechRecognizer.ERROR_CANNOT_CHECK_SUPPORT
        if (unsupported && segmented) {
            segmented = false // Same on-device service, never a cloud fallback.
        } else if (error != null && error != SpeechRecognizer.ERROR_NO_MATCH &&
                   error != SpeechRecognizer.ERROR_SPEECH_TIMEOUT) {
            finishCapture("음성 인식 실패 [$error] · 남은 초안을 확인하거나 텍스트로 진행해 주세요."); return
        }
        if (error == SpeechRecognizer.ERROR_NO_MATCH || error == SpeechRecognizer.ERROR_SPEECH_TIMEOUT) {
            if (++emptyAttempts >= 3) { finishCapture("음성 대기 종료 · 초안 확인 후 다시 시작하거나 텍스트로 계속해 주세요."); return }
        } else emptyAttempts = 0
        val session = capture.session
        notifyState("음성 입력 이어 듣는 중 · 짧은 재연결 사이에 빠진 단어는 초안에서 확인해 주세요.")
        // Start again only after the previous terminal callback, never onEndOfSpeech.
        handler.postDelayed({
            if (!disposed && session == capture.session && capture.canContinue(SystemClock.elapsedRealtime())) startAttempt()
        }, 200)
    }
    private fun listener(token: Long) = object : RecognitionListener {
        private fun current() = !disposed && capture.accepts(token)
        private fun text(results: Bundle?) = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
        override fun onReadyForSpeech(params: Bundle?) {}
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(value: Float) {} // Never a competence score.
        override fun onBufferReceived(buffer: ByteArray?) {} // Never save audio.
        override fun onEndOfSpeech() {} // A sentence boundary is not the user's stop action.
        override fun onEvent(eventType: Int, params: Bundle?) {}
        override fun onPartialResults(results: Bundle?) {
            if (current()) { draft.partial(text(results)); publish() }
        }
        override fun onSegmentResults(segmentResults: Bundle) {
            if (current()) { draft.segment(text(segmentResults)); publish(); if (draft.full) stop() }
        }
        override fun onEndOfSegmentedSession() { if (current()) terminal(token) }
        override fun onResults(results: Bundle?) {
            if (!current()) return
            val value = text(results)
            if (value.isNotBlank()) draft.final(value)
            terminal(token, if (value.isBlank() && draft.text.isBlank()) SpeechRecognizer.ERROR_NO_MATCH else null)
        }
        override fun onError(error: Int) { if (current()) terminal(token, error) }
    }

    fun stop() {
        if (!listening || capture.stopping) return
        capture.requestStop()
        if (!capture.inFlight) { finishCapture(); return }
        val session = capture.session
        notifyState("인식 마치는 중 · 마지막 전사 결과를 기다립니다.")
        try { recognizer?.stopListening() }
        catch (_: Exception) { finishCapture("음성 중지 오류 · 남은 초안 확인 또는 텍스트 대안 가능"); return }
        handler.postDelayed({
            if (!disposed && capture.session == session && listening) {
                finishCapture("음성 결과 시간 초과 · 남은 초안 확인 또는 텍스트 대안 가능")
            }
        }, 5000)
    }
    fun cancel() {
        val wasListening = listening
        generation++; capture.cancel()
        recognizer?.cancel(); tts?.stop()
        if (wasListening) status = "음성 취소 · 남은 초안은 미확인 상태입니다."
        changed()
    }
    fun speak(text: String) {
        if (!localTtsReady || listening || disposed) return
        tts?.speak(text.take(3500), TextToSpeech.QUEUE_FLUSH, null, "cg-question")
    }
    fun dispose() {
        cancel(); disposed = true; handler.removeCallbacksAndMessages(null)
        recognizer?.destroy(); recognizer = null
        tts?.shutdown(); tts = null
    }
}
