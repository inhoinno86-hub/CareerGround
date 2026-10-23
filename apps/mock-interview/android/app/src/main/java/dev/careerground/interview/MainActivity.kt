package dev.careerground.interview

import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.lifecycle.ViewModelProvider

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        setContent { InterviewApp() }
    }
    override fun onStop() {
        ViewModelProvider(this)[InterviewModel::class.java].stopVoice()
        super.onStop()
    }
}
