package dev.careerground.interview

import org.junit.Assert.*
import org.junit.Test
import java.io.ByteArrayInputStream

class SelectedFilesTest {
    @Test fun readsExactLimitAndRejectsOneExtraByte() {
        assertArrayEquals(byteArrayOf(1, 2, 3), SelectedFiles.readBounded(ByteArrayInputStream(byteArrayOf(1, 2, 3)), 3))
        assertThrows(IllegalArgumentException::class.java) {
            SelectedFiles.readBounded(ByteArrayInputStream(byteArrayOf(1, 2, 3, 4)), 3)
        }
    }

    @Test fun keepsUtf8OriginalBytesAndProducesRawFileHash() {
        val raw = "합성 파일\n".toByteArray(Charsets.UTF_8)
        assertArrayEquals(raw, SelectedFiles.readBounded(ByteArrayInputStream(raw), raw.size))
        assertEquals(64, SelectedFiles.sha256(raw).length)
        assertNotEquals(SelectedFiles.sha256(raw), SelectedFiles.sha256(raw + byteArrayOf(32)))
    }
}
