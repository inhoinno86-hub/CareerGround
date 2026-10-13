package dev.careerground.interview

import android.net.Uri
import androidx.test.ext.junit.runners.AndroidJUnit4
import net.openid.appauth.AuthorizationRequest
import net.openid.appauth.AuthorizationResponse
import net.openid.appauth.AuthorizationServiceConfiguration
import net.openid.appauth.ResponseTypeValues
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Synthetic SDK/callback checks on Android; these do not execute a provider login. */
@RunWith(AndroidJUnit4::class)
class OidcBoundaryTest {
    @Test fun callbackRequiresExactSchemeHostlessPathAndNoFragment() {
        val scheme = "dev.careerground.interview.dev"
        assertTrue(OidcChecks.acceptsRedirect(Uri.parse("$scheme:/oauth2redirect?state=synthetic"), scheme))
        for (value in listOf("other:/oauth2redirect", "$scheme:/wrong", "$scheme://host/oauth2redirect",
            "$scheme:/oauth2redirect#unexpected", "$scheme:/oauth2redirect/")) {
            assertFalse(OidcChecks.acceptsRedirect(Uri.parse(value), scheme))
        }
        assertFalse(OidcChecks.acceptsRedirect(null, scheme))
    }

    @Test fun responseMustMatchStateAndEntirePendingRequest() {
        val config = AuthorizationServiceConfiguration(Uri.parse("https://synthetic.invalid/authorize"),
            Uri.parse("https://synthetic.invalid/token"))
        fun request(client: String) = AuthorizationRequest.Builder(config, client, ResponseTypeValues.CODE,
            Uri.parse("dev.careerground.interview.dev:/oauth2redirect")).build()
        val expected = request("synthetic-client")
        assertEquals("S256", expected.codeVerifierChallengeMethod)
        assertNotNull(expected.nonce)
        assertNotNull(expected.state)
        val valid = AuthorizationResponse.Builder(expected).setState(expected.state).setAuthorizationCode("synthetic-code").build()
        OidcChecks.requireResponse(expected, valid)
        val wrongState = AuthorizationResponse.Builder(expected).setState("wrong").setAuthorizationCode("synthetic-code").build()
        val changedRequest = AuthorizationResponse.Builder(request("other-client")).setState(expected.state)
            .setAuthorizationCode("synthetic-code").build()
        for (response in listOf(wrongState, changedRequest)) {
            assertThrows(IllegalArgumentException::class.java) { OidcChecks.requireResponse(expected, response) }
        }
    }
}
