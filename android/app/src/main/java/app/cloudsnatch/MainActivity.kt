package app.cloudsnatch

import android.app.Application
import android.app.DownloadManager
import android.content.ContentUris
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.provider.MediaStore
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONException
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.io.IOException
import java.net.URI
import java.net.URISyntaxException
import java.net.URLDecoder
import java.nio.charset.StandardCharsets
import java.security.MessageDigest

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            CloudSnatchApp()
        }
    }
}

internal data class CategoryStatus(
    val status: String = "Waiting",
    val count: Int = 0,
    val detail: String = "",
)

internal data class LatestItem(
    val category: String,
    val count: Int,
    val title: String,
    val json: String,
    val csv: String,
    val truncated: Boolean,
    val checkpoint: Boolean,
)

internal data class ExportUiState(
    val profileUrl: String = "",
    val status: String = "Enter a public profile URL to begin.",
    val running: Boolean = false,
    val categories: Map<String, CategoryStatus> = emptyMap(),
    val latestItem: LatestItem? = null,
    val error: String? = null,
    val downloadUris: List<Uri> = emptyList(),
)

internal fun normalizeProfileUrl(value: String): String {
    val uri = try {
        URI(value.trim())
    } catch (error: URISyntaxException) {
        throw IllegalArgumentException(
            "Enter a SoundCloud profile URL, such as https://soundcloud.com/artist.",
            error,
        )
    }
    val scheme = uri.scheme?.lowercase()
    val host = uri.host?.lowercase()
    require(scheme == "http" || scheme == "https") {
        "Enter a SoundCloud profile URL, such as https://soundcloud.com/artist."
    }
    require(host in setOf("soundcloud.com", "www.soundcloud.com", "m.soundcloud.com")) {
        "Enter a SoundCloud profile URL."
    }
    require(uri.port == -1 && uri.rawUserInfo == null && uri.rawQuery == null && uri.rawFragment == null) {
        "Enter a profile URL only, such as https://soundcloud.com/artist."
    }
    val profilePath = uri.rawPath.orEmpty().split('/').filter(String::isNotEmpty)
    require(profilePath.size == 1) {
        "Enter a profile URL only, such as https://soundcloud.com/artist."
    }
    return "https://soundcloud.com/${profilePath.single()}"
}

internal fun accountFolderName(profileUrl: String): String {
    val normalized = normalizeProfileUrl(profileUrl)
    val encodedName = URI(normalized).rawPath.orEmpty().trim('/')
    val displayName = URLDecoder.decode(encodedName, StandardCharsets.UTF_8.name())
        .replace(Regex("[^A-Za-z0-9._-]+"), "-")
        .trim('.', '-', '_')
        .ifEmpty { "soundcloud-account" }
    val suffix = MessageDigest.getInstance("SHA-256")
        .digest(normalized.toByteArray(Charsets.UTF_8))
        .take(4)
        .joinToString("") { (it.toInt() and 0xff).toString(16).padStart(2, '0') }
    return "$displayName-$suffix"
}

internal class ExportViewModel(application: Application) : AndroidViewModel(application) {
    private val _state = kotlinx.coroutines.flow.MutableStateFlow(ExportUiState())
    val state = _state.asStateFlow()
    private var exportJob: Job? = null

    fun startExport(profileInput: String, force: Boolean = false) {
        if (exportJob?.isActive == true) return
        val profile = try {
            normalizeProfileUrl(profileInput)
        } catch (error: IllegalArgumentException) {
            _state.value = _state.value.copy(error = error.message)
            return
        }

        val outputDirectory = File(getApplication<Application>().filesDir, "accounts/${accountFolderName(profile)}")
        _state.value = _state.value.copy(
            profileUrl = profile,
            status = "Preparing the public collection export.",
            running = true,
            error = null,
            latestItem = null,
            downloadUris = emptyList(),
        )
        exportJob = viewModelScope.launch {
            try {
                val oldReport = withContext(Dispatchers.IO) {
                    readReport(File(outputDirectory, "report.json"))
                }
                if (!force && oldReport.isNotEmpty()) {
                    _state.value = _state.value.copy(categories = oldReport)
                }

                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(getApplication()))
                }
                val progressFile = File(outputDirectory, "mobile-progress.json")
                val export = async(Dispatchers.IO) {
                    Python.getInstance()
                        .getModule("mobile_export")
                        .callAttr("run_export", profile, outputDirectory.absolutePath, force)
                        .toString()
                }
                while (isActive && !export.isCompleted) {
                    val progress = try {
                        withContext(Dispatchers.IO) { readProgress(progressFile) }
                    } catch (error: JSONException) {
                        _state.value = _state.value.copy(
                            error = "Live progress preview could not be read: ${error.message}",
                        )
                        null
                    } catch (error: IOException) {
                        _state.value = _state.value.copy(
                            error = "Live progress preview could not be read: ${error.message}",
                        )
                        null
                    }
                    if (progress != null) {
                        _state.value = _state.value.copy(
                            status = "${progress.first} · ${progress.second.count} items · ${progress.second.status}",
                            categories = _state.value.categories + (progress.first to progress.second),
                            latestItem = progress.third ?: _state.value.latestItem,
                            error = _state.value.error?.takeUnless {
                                it.startsWith("Live progress preview could not be read:")
                            },
                        )
                    }
                    delay(900)
                }

                val reportJson = export.await()
                val report = JSONObject(reportJson)
                val categories = parseCategories(report)
                val publishResult = withContext(Dispatchers.IO) {
                    DownloadPublisher.publish(getApplication(), profile, outputDirectory)
                }
                val failed = categories.values.any { it.status == "failed" }
                _state.value = _state.value.copy(
                    status = if (failed) "Export finished with errors. Saved files are in Downloads/CloudSnatch."
                    else "Export complete. Saved files are in Downloads/CloudSnatch.",
                    running = false,
                    categories = categories,
                    latestItem = _state.value.latestItem?.copy(checkpoint = true),
                    error = publishResult.error,
                    downloadUris = publishResult.uris,
                )
            } catch (error: Exception) {
                _state.value = _state.value.copy(
                    status = "Export stopped. Resume it to continue from the last checkpoint.",
                    running = false,
                    error = error.message ?: error.javaClass.simpleName,
                )
            }
        }
    }

    fun showDownloads() {
        try {
            val intent = Intent(DownloadManager.ACTION_VIEW_DOWNLOADS)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            getApplication<Application>().startActivity(intent)
        } catch (_: android.content.ActivityNotFoundException) {
            _state.value = _state.value.copy(error = "No Downloads app is available on this device.")
        }
    }

    fun clearError() {
        if (_state.value.error != null) {
            _state.value = _state.value.copy(error = null)
        }
    }

    fun shareExports() {
        val context = getApplication<Application>()
        val uris = _state.value.downloadUris
        if (uris.isEmpty()) return
        val clip = android.content.ClipData.newUri(context.contentResolver, "CloudSnatch exports", uris.first())
        uris.drop(1).forEach { clip.addItem(android.content.ClipData.Item(it)) }
        val shareIntent = Intent(Intent.ACTION_SEND_MULTIPLE).apply {
            type = "*/*"
            putParcelableArrayListExtra(Intent.EXTRA_STREAM, ArrayList(uris))
            clipData = clip
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        context.startActivity(Intent.createChooser(shareIntent, "Share CloudSnatch exports").apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        })
    }

    private fun readReport(path: File): Map<String, CategoryStatus> =
        if (path.isFile) parseCategories(JSONObject(path.readText()))
        else emptyMap()

    private fun readProgress(path: File): Triple<String, CategoryStatus, LatestItem?>? {
        if (!path.isFile) return null
        val progress = JSONObject(path.readText())
        val category = progress.optString("category")
        val latest = progress.optJSONObject("latest_item")?.let {
            LatestItem(
                category = it.optString("category"),
                count = it.optInt("count"),
                title = it.optString("title"),
                json = it.optString("json"),
                csv = it.optString("csv"),
                truncated = it.optBoolean("json_truncated"),
                checkpoint = it.optBoolean("checkpoint"),
            )
        }
        return Triple(
            category,
            CategoryStatus("Working", progress.optInt("count"), progress.optString("message")),
            latest,
        )
    }
}

private data class PublishResult(val uris: List<Uri>, val error: String?)

private object DownloadPublisher {
    private val fileNames = listOf("likes.json", "likes.csv", "playlists.json", "playlists.csv", "report.json")

    fun publish(context: Context, profileUrl: String, outputDirectory: File): PublishResult {
        val resolver = context.contentResolver
        val relativePath = "${Environment.DIRECTORY_DOWNLOADS}/CloudSnatch/${accountFolderName(profileUrl)}/"
        val collection = MediaStore.Downloads.EXTERNAL_CONTENT_URI
        val saved = mutableListOf<Uri>()
        try {
            for (name in fileNames) {
                val source = File(outputDirectory, name)
                if (!source.isFile) continue
                val oldFiles = findPrevious(resolver, collection, relativePath, name)
                val stagedName = ".cloudsnatch-${java.util.UUID.randomUUID()}.pending"
                val values = ContentValues().apply {
                    put(MediaStore.Downloads.DISPLAY_NAME, stagedName)
                    put(MediaStore.Downloads.MIME_TYPE, if (name.endsWith(".csv")) "text/csv" else "application/json")
                    put(MediaStore.Downloads.RELATIVE_PATH, relativePath)
                    put(MediaStore.Downloads.IS_PENDING, 1)
                }
                val uri = resolver.insert(collection, values)
                    ?: throw IOException("Android could not create $name in Downloads.")
                try {
                    resolver.openOutputStream(uri, "w")?.use { destination ->
                        FileInputStream(source).use { it.copyTo(destination) }
                    } ?: throw IOException("Android could not write $name in Downloads.")
                    val ready = ContentValues().apply {
                        put(MediaStore.Downloads.DISPLAY_NAME, name)
                        put(MediaStore.Downloads.IS_PENDING, 0)
                    }
                    if (resolver.update(uri, ready, null, null) != 1) {
                        throw IOException("Android could not finish saving $name in Downloads.")
                    }
                    oldFiles.forEach { resolver.delete(it, null, null) }
                    saved += uri
                } catch (error: Exception) {
                    resolver.delete(uri, null, null)
                    throw error
                }
            }
        } catch (error: Exception) {
            return PublishResult(saved, "Export is checkpointed on this device, but saving to Downloads failed: ${error.message}")
        }
        return PublishResult(saved, null)
    }

    private fun findPrevious(
        resolver: android.content.ContentResolver,
        collection: Uri,
        relativePath: String,
        name: String,
    ): List<Uri> {
        val selection = "${MediaStore.Downloads.DISPLAY_NAME}=? AND ${MediaStore.Downloads.RELATIVE_PATH}=?"
        val matches = mutableListOf<Uri>()
        resolver.query(
            collection,
            arrayOf(MediaStore.Downloads._ID),
            selection,
            arrayOf(name, relativePath),
            null,
        )?.use { cursor ->
            val idColumn = cursor.getColumnIndexOrThrow(MediaStore.Downloads._ID)
            while (cursor.moveToNext()) {
                matches += ContentUris.withAppendedId(collection, cursor.getLong(idColumn))
            }
        }
        return matches
    }
}

private fun parseCategories(report: JSONObject): Map<String, CategoryStatus> {
    val result = mutableMapOf<String, CategoryStatus>()
    val source = report.optJSONObject("categories") ?: return result
    for (name in listOf("likes", "playlists", "followings")) {
        val category = source.optJSONObject(name) ?: continue
        result[name] = CategoryStatus(
            status = category.optString("status", "Waiting"),
            count = category.optInt("count"),
            detail = category.optString("error").ifEmpty { category.optString("reason") },
        )
    }
    return result
}

private val accentColors = mapOf(
    "Orange" to android.graphics.Color.rgb(255, 136, 85),
    "Amber" to android.graphics.Color.rgb(255, 193, 91),
    "Blue" to android.graphics.Color.rgb(122, 185, 255),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CloudSnatchApp(model: ExportViewModel = viewModel()) {
    val state by model.state.collectAsState()
    val context = LocalContext.current
    var profileUrl by rememberSaveable { mutableStateOf("") }
    var selectedAccent by rememberSaveable {
        mutableStateOf(context.getSharedPreferences("appearance", Context.MODE_PRIVATE).getString("accent", "Orange") ?: "Orange")
    }
    var confirmRefetch by rememberSaveable { mutableStateOf(false) }
    val accent = androidx.compose.ui.graphics.Color(accentColors[selectedAccent] ?: accentColors.getValue("Orange"))
    val colorScheme = androidx.compose.material3.darkColorScheme(
        primary = accent,
        onPrimary = androidx.compose.ui.graphics.Color(0xFF241008),
        primaryContainer = accent.copy(alpha = 0.22f),
        onPrimaryContainer = androidx.compose.ui.graphics.Color(0xFFFFE1D2),
        secondary = androidx.compose.ui.graphics.Color(0xFFFFC15B),
        background = androidx.compose.ui.graphics.Color(0xFF111112),
        surface = androidx.compose.ui.graphics.Color(0xFF19191B),
        surfaceVariant = androidx.compose.ui.graphics.Color(0xFF242426),
        onSurface = androidx.compose.ui.graphics.Color(0xFFF5F4F2),
        onSurfaceVariant = androidx.compose.ui.graphics.Color(0xFFC0BCBA),
        outline = androidx.compose.ui.graphics.Color(0xFF555155),
        error = androidx.compose.ui.graphics.Color(0xFFFF9DA7),
    )

    MaterialTheme(colorScheme = colorScheme) {
        Scaffold(
            contentWindowInsets = WindowInsets.safeDrawing,
            topBar = {
                TopAppBar(
                    title = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Surface(
                                color = MaterialTheme.colorScheme.primary,
                                shape = MaterialTheme.shapes.small,
                                modifier = Modifier.size(36.dp),
                            ) {
                                androidx.compose.foundation.layout.Box(contentAlignment = Alignment.Center) {
                                    Text("CS", color = MaterialTheme.colorScheme.onPrimary, fontWeight = FontWeight.Black)
                                }
                            }
                            Spacer(Modifier.width(10.dp))
                            Column {
                                Text("CLOUDSNATCH", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                                Text("SoundCloud likes & playlists", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    },
                    actions = {
                        AssistChip(
                            onClick = {},
                            label = { Text("ON DEVICE") },
                            modifier = Modifier.padding(end = 8.dp),
                        )
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                )
            },
        ) { innerPadding ->
            BoxWithConstraints(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
                    .imePadding(),
            ) {
                val wide = maxWidth >= 640.dp
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .verticalScroll(rememberScrollState())
                        .padding(horizontal = if (wide) 32.dp else 20.dp)
                        .padding(top = 20.dp, bottom = 32.dp),
                    verticalArrangement = Arrangement.spacedBy(20.dp),
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(
                            "Keep the public collections you love.",
                            style = MaterialTheme.typography.headlineMedium,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            "Save likes and playlists as CSV and JSON files. No login, no audio downloads.",
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }

                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        OutlinedTextField(
                            value = profileUrl,
                            onValueChange = {
                                profileUrl = it
                                model.clearError()
                            },
                            modifier = Modifier
                                .fillMaxWidth()
                                .semantics { contentDescription = "Public SoundCloud profile URL" },
                            enabled = !state.running,
                            label = { Text("Public profile URL") },
                            placeholder = { Text("https://soundcloud.com/artist") },
                            singleLine = true,
                            isError = state.error != null,
                        )
                        Button(
                            onClick = { model.startExport(profileUrl) },
                            enabled = !state.running,
                            modifier = Modifier.fillMaxWidth().height(52.dp),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = MaterialTheme.colorScheme.primary,
                                contentColor = MaterialTheme.colorScheme.onPrimary,
                            ),
                        ) {
                            if (state.running) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(20.dp),
                                    color = MaterialTheme.colorScheme.onPrimary,
                                    strokeWidth = 2.dp,
                                )
                                Spacer(Modifier.width(10.dp))
                                Text("Exporting public collections…")
                            } else {
                                Text("Export or resume")
                            }
                        }
                        Text(
                            "Keep CloudSnatch open while it runs. Interrupted exports resume from a local checkpoint.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }

                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Accent color", style = MaterialTheme.typography.titleSmall)
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            accentColors.keys.forEach { colorName ->
                                FilterChip(
                                    selected = selectedAccent == colorName,
                                    onClick = {
                                        selectedAccent = colorName
                                        context.getSharedPreferences("appearance", Context.MODE_PRIVATE)
                                            .edit().putString("accent", colorName).apply()
                                    },
                                    label = { Text(colorName) },
                                    modifier = Modifier.semantics { contentDescription = "$colorName accent color" },
                                )
                            }
                        }
                    }

                    Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.45f))
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("Export status", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                        Text(state.status, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (wide) {
                            Row(horizontalArrangement = Arrangement.spacedBy(28.dp)) {
                                CategoryLine("Likes", state.categories["likes"], Modifier.weight(1f))
                                CategoryLine("Playlists", state.categories["playlists"], Modifier.weight(1f))
                            }
                        } else {
                            CategoryLine("Likes", state.categories["likes"], Modifier.fillMaxWidth())
                            CategoryLine("Playlists", state.categories["playlists"], Modifier.fillMaxWidth())
                        }
                        Text(
                            "Following and follower lists are not supported.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }

                    state.latestItem?.let { LatestItemPreview(it) }
                    state.error?.let {
                        Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
                    }

                    if (state.downloadUris.isNotEmpty()) {
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            TextButton(onClick = model::showDownloads, modifier = Modifier.weight(1f).heightIn(min = 48.dp)) {
                                Text("Open Downloads")
                            }
                            Button(onClick = model::shareExports, modifier = Modifier.weight(1f).heightIn(min = 48.dp)) {
                                Text("Share files")
                            }
                        }
                    }
                    if (!state.running && state.profileUrl.isNotEmpty()) {
                        TextButton(onClick = { confirmRefetch = true }, modifier = Modifier.heightIn(min = 48.dp)) {
                            Text("Start over and replace saved files")
                        }
                    }

                    Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.45f))
                    Text(
                        "Only publicly visible metadata is exported. CloudSnatch does not add analytics or send your archive to a CloudSnatch server. SoundCloud requests are made directly from your device; public collection results are not guaranteed complete.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }

    if (confirmRefetch) {
        AlertDialog(
            onDismissRequest = { confirmRefetch = false },
            title = { Text("Start this profile over?") },
            text = { Text("This replaces the saved likes and playlist files for this profile. Other profiles are not affected.") },
            confirmButton = {
                TextButton(onClick = {
                    confirmRefetch = false
                    model.startExport(profileUrl, force = true)
                }) { Text("Replace files") }
            },
            dismissButton = {
                TextButton(onClick = { confirmRefetch = false }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun CategoryLine(name: String, item: CategoryStatus?, modifier: Modifier) {
    Column(modifier.padding(vertical = 4.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        val status = item?.status ?: "Waiting"
        val count = item?.count?.let { " · ${it} items" }.orEmpty()
        Text(
            text = "$status$count${item?.detail?.let { " · $it" }.orEmpty()}",
            style = MaterialTheme.typography.bodySmall,
            color = if (status == "failed") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 4,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            if (name == "Likes") "likes.json · likes.csv" else "playlists.json · playlists.csv",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun LatestItemPreview(item: LatestItem) {
    var expanded by rememberSaveable(item.category, item.count) { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.45f))
        TextButton(
            onClick = { expanded = !expanded },
            modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
        ) {
            Text(if (expanded) "Hide latest item" else "Show latest item")
        }
        if (expanded) {
            Text(
                "${item.category} · item ${item.count} · ${if (item.checkpoint) "checkpoint saved" else "JSON checkpoint pending"}",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(item.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Surface(color = MaterialTheme.colorScheme.surfaceVariant, shape = MaterialTheme.shapes.small) {
                Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("JSON", style = MaterialTheme.typography.labelLarge)
                    Text(
                        item.json + if (item.truncated) "\n… preview shortened; open the saved file for the full record." else "",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.45f))
                    Text("CSV row", style = MaterialTheme.typography.labelLarge)
                    Text(item.csv, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}
