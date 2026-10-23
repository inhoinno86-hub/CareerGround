package dev.careerground.interview

import android.net.Uri
import net.openid.appauth.AuthorizationRequest
import net.openid.appauth.AuthorizationResponse

object OidcChecks {
    fun acceptsRedirect(uri: Uri?, scheme: String): Boolean = uri != null &&
        uri.scheme == scheme && uri.authority == null && uri.path == "/oauth2redirect" &&
        uri.fragment == null

    fun requireResponse(expected: AuthorizationRequest, response: AuthorizationResponse) {
        require(response.state == expected.state &&
            response.request.jsonSerializeString() == expected.jsonSerializeString()) { "OIDC_STATE_MISMATCH" }
    }
}
