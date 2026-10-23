package dev.careerground.interview

/** RAM-only user recording window, independent of a recognizer's utterance endpoints. */
internal class VoiceCaptureWindow(private val maxMillis: Long = 120_000) {
    var active = false; private set
    var stopping = false; private set
    var session = 0L; private set
    var inFlight = false; private set
    private var deadline = 0L
    private var attempt = 0L
    enum class Next { IGNORE, CONTINUE, FINISH }

    fun begin(now: Long): Long {
        cancel()
        active = true
        deadline = now + maxMillis
        return session
    }
    fun canContinue(now: Long) = active && !stopping && now < deadline
    fun nextAttempt(now: Long): Long? {
        if (!canContinue(now) || inFlight) return null
        inFlight = true
        return ++attempt
    }
    fun accepts(token: Long) = active && inFlight && token == attempt
    fun terminal(token: Long, now: Long): Next {
        if (!accepts(token)) return Next.IGNORE
        inFlight = false
        return if (canContinue(now)) Next.CONTINUE else Next.FINISH
    }
    fun requestStop() { if (active) stopping = true }
    fun cancel() {
        active = false; stopping = false; inFlight = false; session++
    }
}

/** Partial hypotheses replace each other; finalized segments accumulate once. */
internal class VoiceTranscript(private val maxChars: Int = 20_000) {
    private val segments = mutableListOf<String>()
    private var partial = ""
    private var attemptStart = 0
    val text: String get() = (segments + partial).filter { it.isNotBlank() }.joinToString(" ").take(maxChars)
    val full: Boolean get() = text.length >= maxChars
    fun clear() { segments.clear(); partial = ""; attemptStart = 0 }
    fun beginAttempt() { attemptStart = segments.size; partial = "" }
    fun partial(value: String) { partial = value.trim().take(maxChars) }
    fun segment(value: String) {
        val used = segments.joinToString(" ").length
        val room = maxChars - used - if (segments.isEmpty()) 0 else 1
        if (value.isNotBlank() && room > 0) segments.add(value.trim().take(room))
        partial = ""
    }
    fun final(value: String) {
        val completed = segments.drop(attemptStart).joinToString(" ")
        if (completed.isBlank()) segment(value)
        else if (value.trim().startsWith(completed)) segment(value.trim().removePrefix(completed))
        // Segmented services normally end with onEndOfSegmentedSession. A later
        // aggregate onResults must not append already emitted segments twice.
    }
    fun preservePartial() { if (partial.isNotBlank()) segment(partial) }
}
