package app.cloudsnatch

import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class HomeScreenTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun showsSnapshotControlsAndUnsupportedCollections() {
        composeRule.onNodeWithText("CLOUDSNATCH").fetchSemanticsNode()
        composeRule.onNodeWithText("SoundCloud snapshot tool").fetchSemanticsNode()
        composeRule.onNodeWithText("Public profile URL").fetchSemanticsNode()
        composeRule.onNodeWithText("Create snapshot or resume").fetchSemanticsNode()
        composeRule.onNodeWithText("Snapshot progress").fetchSemanticsNode()
        composeRule.onNodeWithText("Live track IDs · 0").fetchSemanticsNode()
        composeRule.onNodeWithText("Following and follower lists are not supported.").fetchSemanticsNode()
    }
}
