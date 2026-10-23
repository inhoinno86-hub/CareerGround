package dev.careerground.interview

import android.os.Bundle
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertFalse
import org.junit.Test
import org.junit.runner.RunWith

/** Real device metadata query only. PASS is not a successful microphone/STT run. */
@RunWith(AndroidJUnit4::class)
class DeviceVoiceProbeTest {
    @Test fun queryOnDeviceKoreanAndLocalTtsWithoutRecordingOrDownloading() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        lateinit var voice: DeviceVoice
        instrumentation.runOnMainSync {
            voice = DeviceVoice(instrumentation.targetContext, {}, { _, _ ->
                throw AssertionError("Metadata probe must never capture a transcript")
            })
            voice.check()
        }
        Thread.sleep(12000)
        instrumentation.runOnMainSync {
            val report = Bundle().apply {
                putString("careerground_voice_status", voice.status)
                putBoolean("careerground_on_device_korean_ready", voice.ready)
                putBoolean("careerground_local_korean_tts_ready", voice.localTtsReady)
                putString("careerground_microphone_test", "NOT_RUN")
            }
            instrumentation.sendStatus(2, report)
            assertFalse(voice.listening)
            voice.dispose()
        }
    }
}
