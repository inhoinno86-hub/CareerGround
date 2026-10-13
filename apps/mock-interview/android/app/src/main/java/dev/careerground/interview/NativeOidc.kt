package dev.careerground.interview

import android.content.Context
import android.content.Intent
import android.net.Uri
import kotlinx.coroutines.suspendCancellableCoroutine
import net.openid.appauth.*
import net.openid.appauth.connectivity.ConnectionBuilder
import org.json.JSONObject
import java.net.HttpURLConnection
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** Public configuration only; pending authorization and tokens live in this process's RAM. */
class NativeOidc(context: Context) {
    private val config = run {
        check(BuildConfig.DEBUG) { "RELEASE_AUTH_NOT_CONFIGURED" }
        context.assets.open("auth0-dev.public.json").use {
            JSONObject(String(SelectedFiles.readBounded(it, 16384), Charsets.UTF_8))
        }
    }
    private val issuer = config.getString("issuer")
    private val redirect = Uri.parse(config.getString("redirect_uri"))
    private val connectionBuilder = ConnectionBuilder { uri ->
        require(uri.toString() in setOf(issuer + ".well-known/openid-configuration",
            issuer + "oauth/token")) { "OIDC_ENDPOINT_REJECTED" }
        (uri.toString().let { java.net.URI(it).toURL().openConnection() } as HttpURLConnection).apply {
            instanceFollowRedirects = false; connectTimeout = 10000; readTimeout = 20000
        }
    }
    private val service = AuthorizationService(context.applicationContext,
        AppAuthConfiguration.Builder().setConnectionBuilder(connectionBuilder).build())
    private var pending: AuthorizationRequest? = null

    suspend fun begin(): Intent {
        check(pending == null) { "OIDC_ALREADY_PENDING" }
        val discovered = suspendCancellableCoroutine<AuthorizationServiceConfiguration> { continuation ->
            AuthorizationServiceConfiguration.fetchFromIssuer(Uri.parse(issuer), { result, error ->
                if (continuation.isActive) {
                    if (result != null && error == null) continuation.resume(result)
                    else continuation.resumeWithException(IllegalStateException("OIDC_DISCOVERY_FAILED"))
                }
            }, connectionBuilder)
        }
        require(discovered.authorizationEndpoint.toString() == issuer + "authorize" &&
            discovered.tokenEndpoint.toString() == issuer + "oauth/token" &&
            discovered.discoveryDoc?.issuer?.toString() == issuer &&
            discovered.discoveryDoc?.docJson?.optJSONArray("code_challenge_methods_supported")
                ?.let { values -> (0 until values.length()).any { values.optString(it) == "S256" } } == true
        ) { "OIDC_DISCOVERY_MISMATCH" }
        val request = AuthorizationRequest.Builder(discovered, config.getString("client_id"),
            ResponseTypeValues.CODE, redirect)
            .setScope(config.getJSONArray("scopes").let { values ->
                (0 until values.length()).joinToString(" ") { values.getString(it) } })
            .setPrompt("login")
            .setAdditionalParameters(mapOf("audience" to config.getString("audience"))).build()
        check(request.codeVerifierChallengeMethod == "S256" && request.state != null && request.nonce != null)
        return service.getAuthorizationRequestIntent(request).also { pending = request }
    }

    suspend fun complete(data: Intent?): LoginToken {
        val expected = pending
        pending = null // A callback can be consumed only once. Process loss fails closed.
        require(expected != null) { "OIDC_NO_PENDING_REQUEST" }
        val response = data?.let(AuthorizationResponse::fromIntent)
        val error = data?.let(AuthorizationException::fromIntent)
        require(response != null && error == null && response.authorizationCode != null) { "OIDC_CANCELLED_OR_FAILED" }
        OidcChecks.requireResponse(expected, response)
        val tokens = suspendCancellableCoroutine<TokenResponse> { continuation ->
            service.performTokenRequest(response.createTokenExchangeRequest(), NoClientAuthentication.INSTANCE) { result, failure ->
                if (continuation.isActive) {
                    if (result != null && failure == null) continuation.resume(result)
                    else continuation.resumeWithException(IllegalStateException("OIDC_TOKEN_EXCHANGE_FAILED"))
                }
            }
        }
        val token = tokens.accessToken
        val expires = tokens.accessTokenExpirationTime
        // openid was requested: require the ID token whose nonce AppAuth validated.
        require(!tokens.idToken.isNullOrBlank() && tokens.tokenType.equals("Bearer", ignoreCase = true) && token != null &&
            token.length in 1..16384 && expires != null && expires > System.currentTimeMillis()
        ) { "OIDC_TOKEN_RESPONSE_REJECTED" }
        // No AuthState, refresh token, ID token, preferences, or automatic token persistence.
        return LoginToken(token, expires)
    }

    fun cancel() { pending = null }
    fun dispose() { cancel(); service.dispose() }
}

data class LoginToken(val accessToken: String, val expiresAtMillis: Long) {
    override fun toString() = "LoginToken(REDACTED)"
}
