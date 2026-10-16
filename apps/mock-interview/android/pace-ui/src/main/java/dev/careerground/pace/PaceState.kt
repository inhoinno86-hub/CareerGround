package dev.careerground.pace

// Immutable presentation data. Only the owner of the functional state executes actions.
enum class PaceScreen { LOGIN, HOME, IMPORT, REVIEW, INTERVIEW, RESULT }
enum class PaceAction {
    LOGIN, CONNECT_DEV, DISCONNECT, PICK_HANDOFF, RESTORE, PICK_ATTACHMENTS, VALIDATE, REVIEW,
    START, START_FOCUS, GENERATE, SUBMIT, EVALUATE, SKIP, FINISH, PAUSE, CONTINUE, ABORT,
    CHECK_VOICE, START_VOICE, FINISH_VOICE, STOP_VOICE, SPEAK,
    PREPARE_SESSION, PREPARE_SNAPSHOT, PREPARE_RESULT, SAVE,
}
data class PaceQuestion(val id: String, val text: String, val status: String = "pending",
    val references: String = "", val gap: Boolean = false)
data class PaceAnswer(val questionId: String, val text: String, val revision: Int = 1)
data class PaceReviewSection(val title: String, val text: String)
data class PaceFeedback(val answerId: String, val text: String)
data class PaceState(
    val screen: PaceScreen = PaceScreen.HOME,
    val connected: Boolean = true, val busy: Boolean = false, val authenticating: Boolean = false,
    val sessionState: String = "READY", val role: String = "지원 직무", val documentCount: Int = 0,
    val selected: Boolean = false, val validated: Boolean = false, val restored: Boolean = false,
    val attachments: Int = 0, val reviewChecked: Boolean = false, val mode: String = "coaching",
    val aiAvailable: Boolean = false, val actualAi: Boolean = false,
    val questionId: String = "", val questions: List<PaceQuestion> = emptyList(),
    val answers: List<PaceAnswer> = emptyList(), val draft: String = "", val confirmed: Boolean = false,
    val voiceReady: Boolean = false, val listening: Boolean = false, val ttsReady: Boolean = false,
    val voiceStatus: String = "음성 준비 상태를 확인해 주세요.",
    val feedback: List<PaceFeedback> = emptyList(), val candidates: List<String> = emptyList(),
    val documentContent: String = "", val exportReady: Boolean = false, val exportKind: String = "session",
    val reviewSections: List<PaceReviewSection> = emptyList(),
    val message: String = "", val joinCode: String = "", val preview: Boolean = false,
    val focus: Boolean = false,
) {
    val activeQuestions get() = questions.filter { it.status != "stale" }
    val currentQuestion get() = activeQuestions.find { it.id == questionId }
    val currentAnswer get() = answers.lastOrNull { it.questionId == questionId }
    val editable get() = sessionState == "IN_PROGRESS" && !busy && !listening
    val canSubmit get() = editable && currentQuestion != null && confirmed && draft.isNotBlank()
    val showFeedback get() = mode != "simulation" || sessionState in listOf("COMPLETED", "ABORTED")
}
data class PaceCallbacks(
    val action: (PaceAction) -> Unit,
    val navigate: (PaceScreen) -> Unit,
    val editDraft: (String) -> Unit,
    val confirmAnswer: (Boolean) -> Unit,
    val confirmReview: (Boolean) -> Unit,
    val selectMode: (String) -> Unit,
    val selectQuestion: (String) -> Unit,
    val editJoinCode: (String) -> Unit,
)
