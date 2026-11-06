package app.cloudsnatch

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class ProfileUrlTest {
    @Test
    fun normalizesSupportedProfileLinks() {
        assertEquals(
            "https://soundcloud.com/artist",
            normalizeProfileUrl("  https://www.soundcloud.com/artist/  "),
        )
        assertEquals(
            "https://soundcloud.com/artist",
            normalizeProfileUrl("http://m.soundcloud.com/artist"),
        )
    }

    @Test
    fun rejectsCollectionLinksAndOtherHosts() {
        listOf(
            "https://soundcloud.com/artist/likes",
            "https://soundcloud.com.evil.example/artist",
            "https://soundcloud.com/artist?next=elsewhere",
            "https://user@soundcloud.com/artist",
            "https://soundcloud.com:443/artist",
            "not a URL",
        ).forEach { url ->
            try {
                normalizeProfileUrl(url)
                throw AssertionError("Expected $url to be rejected")
            } catch (_: IllegalArgumentException) {
                // Expected: only a SoundCloud profile URL is accepted.
            }
        }
    }

    @Test
    fun profileFoldersAreStableAndSeparate() {
        val first = accountFolderName("https://soundcloud.com/artist-one")
        assertEquals(first, accountFolderName("https://soundcloud.com/artist-one"))
        assertNotEquals(first, accountFolderName("https://soundcloud.com/artist-two"))
    }
}
