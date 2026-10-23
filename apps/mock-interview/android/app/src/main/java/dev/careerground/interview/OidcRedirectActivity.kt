package dev.careerground.interview

import android.app.Activity
import android.os.Bundle
import net.openid.appauth.AuthorizationManagementActivity

/** Scheme-only Android filters cannot constrain a URI without a host; check the path here. */
class OidcRedirectActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val uri = intent?.data
        if (BuildConfig.DEBUG && OidcChecks.acceptsRedirect(uri, BuildConfig.APPLICATION_ID)) {
            startActivity(AuthorizationManagementActivity.createResponseHandlingIntent(this, uri))
        }
        finish()
    }
}
