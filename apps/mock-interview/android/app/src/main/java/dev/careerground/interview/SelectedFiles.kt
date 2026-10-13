package dev.careerground.interview

import android.content.ContentResolver
import android.net.Uri
import android.provider.OpenableColumns
import android.util.JsonReader
import android.util.JsonToken
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.io.StringReader
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.security.MessageDigest

object SelectedFiles {
    const val JSON_LIMIT = 2 * 1024 * 1024
    const val SESSION_LIMIT = 4 * 1024 * 1024
    const val ATTACHMENT_LIMIT = 10 * 1024 * 1024
    const val ATTACHMENTS_TOTAL = 20 * 1024 * 1024

    fun readBounded(stream: InputStream, limit: Int): ByteArray {
        val output = ByteArrayOutputStream()
        val buffer = ByteArray(8192)
        while (true) {
            val n = stream.read(buffer)
            if (n < 0) break
            require(output.size() + n <= limit) { "SIZE_LIMIT" }
            output.write(buffer, 0, n)
        }
        return output.toByteArray()
    }

    fun read(resolver: ContentResolver, uri: Uri, limit: Int): ByteArray =
        requireNotNull(resolver.openInputStream(uri)) { "FILE_UNAVAILABLE" }.use {
            readBounded(it, limit)
        }

    fun name(resolver: ContentResolver, uri: Uri): String {
        val cursor = resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
        val name = cursor?.use { if (it.moveToFirst()) it.getString(0) else null }
        require(name != null && Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}").matches(name)) {
            "ATTACHMENT_PATH"
        }
        return name
    }

    fun sha256(raw: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(raw).joinToString("") { "%02x".format(it) }

    fun strictObject(raw: ByteArray, limit: Int = JSON_LIMIT): JSONObject {
        require(raw.size <= limit) { "SIZE_LIMIT" }
        val decoder = Charsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
            .onUnmappableCharacter(CodingErrorAction.REPORT)
        val text = decoder.decode(ByteBuffer.wrap(raw)).toString()
        JsonReader(StringReader(text)).use { reader ->
            reader.isLenient = false
            walk(reader, 0)
            require(reader.peek() == JsonToken.END_DOCUMENT) { "INVALID_JSON" }
        }
        return JSONObject(text)
    }

    private fun walk(reader: JsonReader, depth: Int, field: String? = null) {
        require(depth <= 64) { "JSON_DEPTH" }
        when (reader.peek()) {
            JsonToken.BEGIN_OBJECT -> {
                reader.beginObject()
                val keys = mutableSetOf<String>()
                while (reader.hasNext()) {
                    val key = reader.nextName()
                    require(keys.add(key)) { "DUPLICATE_JSON_KEY" }
                    walk(reader, depth + 1, key)
                }
                reader.endObject()
            }
            JsonToken.BEGIN_ARRAY -> {
                reader.beginArray()
                var count = 0
                while (reader.hasNext()) {
                    require(++count <= 500) { "ARRAY_LIMIT" }
                    walk(reader, depth + 1)
                }
                reader.endArray()
            }
            JsonToken.STRING -> require(reader.nextString().length <=
                if (depth == 1 && field == "handoff_base64") 2796204 else 20000) { "TEXT_LIMIT" }
            JsonToken.NUMBER -> require(reader.nextString().toDouble().isFinite()) { "INVALID_JSON" }
            JsonToken.BOOLEAN -> reader.nextBoolean()
            JsonToken.NULL -> reader.nextNull()
            else -> error("INVALID_JSON")
        }
    }
}
