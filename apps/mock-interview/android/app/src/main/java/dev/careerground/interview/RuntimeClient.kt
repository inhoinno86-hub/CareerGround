package dev.careerground.interview

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URI

class RuntimeClient(token: String, private val expiresAtMillis: Long? = null) {
    private var token: String? = token
    fun clear() { token = null }
    // Only the approved USB reverse/loopback route. No arbitrary input URL or redirect.
    private val endpoint = "http://127.0.0.1:8765"
    fun request(path: String, method: String = "GET", body: JSONObject? = null): ByteArray {
        require(BuildConfig.DEBUG) { "RELEASE_RUNTIME_NOT_CONFIGURED" }
        require(path.startsWith("/v1/"))
        val accessToken = requireNotNull(token) { "UNAUTHENTICATED" }
        check(expiresAtMillis == null || System.currentTimeMillis() < expiresAtMillis) { "TOKEN_EXPIRED" }
        val connection = URI(endpoint + path).toURL().openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.instanceFollowRedirects = false
            connection.connectTimeout = 10000
            connection.readTimeout = if (path.endsWith("/questions") || path.endsWith("/evaluate")) 105000 else 30000
            connection.setRequestProperty("Authorization", "Bearer $accessToken")
            connection.setRequestProperty("Accept", "application/json")
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                val raw = body.toString().toByteArray(Charsets.UTF_8)
                require(raw.size <= 32 * 1024 * 1024) { "SIZE_LIMIT" }
                connection.setFixedLengthStreamingMode(raw.size)
                connection.outputStream.use { it.write(raw) }
            }
            val code = connection.responseCode
            if (code !in 200..299) {
                val error = connection.errorStream?.use { SelectedFiles.readBounded(it, 65536) }
                val codes = error?.let { runCatching { JSONObject(String(it, Charsets.UTF_8))
                    .optJSONArray("errors")?.toString() }.getOrNull() }
                throw IllegalStateException(codes ?: "RUNTIME_HTTP_$code")
            }
            return connection.inputStream.use {
                SelectedFiles.readBounded(it, 6 * 1024 * 1024)
            }
        } finally {
            connection.disconnect()
        }
    }
}
