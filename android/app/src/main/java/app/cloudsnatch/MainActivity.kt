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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.LinearProgressIndicator
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
    val total: Int? = null,
)

internal data class TrackIdRecord(
    val category: String,
    val id: String,
)

internal data class LatestItem(
    val category: String,
    val count: Int,
    val id: String,
    val playlist: String,
    val title: String,
    val json: String,
    val csv: String,
    val truncated: Boolean,
    val checkpoint: Boolean,
)

internal data class ExportUiState(
    val profileUrl: String = "",
    val status: String = "Enter a public profile URL to create a snapshot.",
    val running: Boolean = false,
    val categories: Map<String, CategoryStatus> = emptyMap(),
    val latestItem: LatestItem? = null,
    val trackIds: List<TrackIdRecord> = emptyList(),
    val snapshotCount: Int = 0,
    val snapshotHistoryLoading: Boolean = false,
    val snapshotComparison: String? = null,
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
    private var snapshotLoadJob: Job? = null
    private var trackIdOffset = 0L
    private val seenTrackIds = mutableSetOf<String>()

    fun startExport(profileInput: String, force: Boolean = false) {
        if (exportJob?.isActive == true) return
        val profile = try {
            normalizeProfileUrl(profileInput)
        } catch (error: IllegalArgumentException) {
            _state.value = _state.value.copy(error = error.message)
            return
        }

        snapshotLoadJob?.cancel()
        val outputDirectory = File(getApplication<Application>().filesDir, "accounts/${accountFolderName(profile)}")
        _state.value = _state.value.copy(
            profileUrl = profile,
            status = "Preparing the public snapshot.",
            running = true,
            error = null,
            latestItem = null,
            categories = emptyMap(),
            trackIds = emptyList(),
            snapshotComparison = null,
            snapshotCount = 0,
            snapshotHistoryLoading = false,
            downloadUris = emptyList(),
        )
        trackIdOffset = 0L
        seenTrackIds.clear()
        exportJob = viewModelScope.launch {
            try {
                val oldSnapshots = withContext(Dispatchers.IO) {
                    if (!Python.isStarted()) Python.start(AndroidPlatform(getApplication()))
                    Python.getInstance().getModule("mobile_export")
                    .callAttr("get_snapshots", outputDirectory.absolutePath).toString()
                }
                _state.value = _state.value.copy(snapshotCount = org.json.JSONArray(oldSnapshots).length())

                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(getApplication()))
                }
                val progressFile = File(outputDirectory, "mobile-progress.json")
                if (!outputDirectory.exists() && !outputDirectory.mkdirs()) {
                    throw IOException("Could not prepare the local snapshot folder.")
                }
                if (progressFile.exists() && !progressFile.delete()) {
                    throw IOException("Could not reset the local progress preview.")
                }
                File(outputDirectory, "mobile-track-ids.jsonl").writeText("")
                val export = async(Dispatchers.IO) {
                    Python.getInstance()
                        .getModule("mobile_export")
                        .callAttr("run_export", profile, outputDirectory.absolutePath, force)
                        .toString()
                }
                while (isActive && !export.isCompleted) {
                    val newTrackIds = withContext(Dispatchers.IO) { readNewTrackIds(progressFile.parentFile) }
                    if (newTrackIds.isNotEmpty()) {
                        _state.value = _state.value.copy(trackIds = _state.value.trackIds + newTrackIds)
                    }
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
                val finalTrackIds = withContext(Dispatchers.IO) { readNewTrackIds(progressFile.parentFile) }
                if (finalTrackIds.isNotEmpty()) {
                    _state.value = _state.value.copy(trackIds = _state.value.trackIds + finalTrackIds)
                }
                val report = JSONObject(reportJson)
                val categories = parseCategories(report)
                val publishResult = withContext(Dispatchers.IO) {
                    DownloadPublisher.publish(getApplication(), profile, outputDirectory)
                }
                val savedSnapshots = withContext(Dispatchers.IO) {
                    Python.getInstance().getModule("mobile_export")
                        .callAttr("get_snapshots", outputDirectory.absolutePath).toString()
                }
                val failed = categories.values.any { it.status == "failed" }
                _state.value = _state.value.copy(
                    status = if (failed) "Snapshot finished with errors. Saved files are in Downloads/CloudSnatch."
                    else "Snapshot complete. Saved files are in Downloads/CloudSnatch.",
                    running = false,
                    categories = categories,
                    snapshotCount = org.json.JSONArray(savedSnapshots).length(),
                    latestItem = _state.value.latestItem?.copy(checkpoint = true),
                    error = publishResult.error,
                    downloadUris = publishResult.uris,
                )
            } catch (error: Exception) {
                _state.value = _state.value.copy(
                    status =                     "Snapshot stopped. Resume it to continue from the last checkpoint.",
                    running = false,
                    error = error.message ?: error.javaClass.simpleName,
                )
            }
        }
    }

    fun loadSnapshots(profileInput: String) {
        val profile = try {
            normalizeProfileUrl(profileInput)
        } catch (_: IllegalArgumentException) {
            snapshotLoadJob?.cancel()
            if (!_state.value.running) {
                _state.value = _state.value.copy(
                    profileUrl = "",
                    snapshotCount = 0,
                    snapshotHistoryLoading = false,
                    snapshotComparison = null,
                    downloadUris = emptyList(),
                )
            }
            return
        }
        if (exportJob?.isActive == true) return
        if (_state.value.profileUrl == profile && _state.value.snapshotCount > 0) return
        snapshotLoadJob?.cancel()
        _state.value = _state.value.copy(
            profileUrl = profile,
            snapshotCount = 0,
            snapshotHistoryLoading = true,
            snapshotComparison = null,
            error = null,
            downloadUris = emptyList(),
        )
        val directory = File(getApplication<Application>().filesDir, "accounts/${accountFolderName(profile)}")
        snapshotLoadJob = viewModelScope.launch {
            try {
                val count = withContext(Dispatchers.IO) {
                    if (!Python.isStarted()) Python.start(AndroidPlatform(getApplication()))
                    val result = Python.getInstance().getModule("mobile_export")
                        .callAttr("get_snapshots", directory.absolutePath).toString()
                    org.json.JSONArray(result).length()
                }
                _state.value = _state.value.copy(
                    profileUrl = profile,
                    snapshotCount = count,
                    snapshotHistoryLoading = false,
                )
            } catch (error: Exception) {
                _state.value = _state.value.copy(
                    snapshotHistoryLoading = false,
                    error = "Could not read local snapshot history: ${error.message}",
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

    fun compareSnapshots() {
        val directory = _state.value.profileUrl.takeIf(String::isNotEmpty)?.let {
            File(getApplication<Application>().filesDir, "accounts/${accountFolderName(it)}")
        } ?: return
        viewModelScope.launch {
            try {
                val comparison = withContext(Dispatchers.IO) {
                    Python.getInstance().getModule("mobile_export")
                        .callAttr("compare_snapshots", directory.absolutePath).toString()
                }
                val result = JSONObject(comparison)
                val categories = result.getJSONObject("categories")
                val lines = listOf("likes", "playlist_tracks", "playlists").map { name ->
                    val item = categories.getJSONObject(name)
                    if (!item.optBoolean("available", true)) {
                        "${name.replace("_", " ")}: not compared (incomplete snapshot)"
                    } else {
                        "${name.replace("_", " ")}: +${item.optInt("added_count")} added · " +
                            "${item.optInt("removed_count")} removed"
                    }
                }
                _state.value = _state.value.copy(
                    snapshotComparison = "${result.getJSONObject("older_snapshot").optString("snapshot_id")} → " +
                        "${result.getJSONObject("newer_snapshot").optString("snapshot_id")}\n" +
                        lines.joinToString("\n"),
                )
            } catch (error: Exception) {
                _state.value = _state.value.copy(error = "Could not compare local snapshots: ${error.message}")
            }
        }
    }

    fun deleteSnapshots() {
        val directory = _state.value.profileUrl.takeIf(String::isNotEmpty)?.let {
            File(getApplication<Application>().filesDir, "accounts/${accountFolderName(it)}")
        } ?: return
        viewModelScope.launch {
            try {
                withContext(Dispatchers.IO) {
                    Python.getInstance().getModule("mobile_export")
                        .callAttr("delete_snapshots", directory.absolutePath)
                }
                _state.value = _state.value.copy(snapshotCount = 0, snapshotComparison = null)
            } catch (error: Exception) {
                _state.value = _state.value.copy(error = "Could not clear snapshot history: ${error.message}")
            }
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

    private fun readNewTrackIds(directory: File?): List<TrackIdRecord> {
        val path = directory?.let { File(it, "mobile-track-ids.jsonl") } ?: return emptyList()
        if (!path.isFile || path.length() < trackIdOffset) return emptyList()
        val records = mutableListOf<TrackIdRecord>()
        java.io.RandomAccessFile(path, "r").use { stream ->
            stream.seek(trackIdOffset)
            while (true) {
                val lineStart = stream.filePointer
                val line = stream.readLine() ?: break
                if (line.isEmpty()) continue
                val value = try {
                    JSONObject(line)
                } catch (_: JSONException) {
                    stream.seek(lineStart)
                    break
                }
                trackIdOffset = stream.filePointer
                val category = value.optString("category")
                val id = value.optString("id")
                val key = "$category:$id"
                if (id.isNotEmpty() && seenTrackIds.add(key)) records += TrackIdRecord(category, id)
            }
        }
        return records
    }

    private fun readProgress(path: File): Triple<String, CategoryStatus, LatestItem?>? {
        if (!path.isFile) return null
        val progress = JSONObject(path.readText())
        val category = progress.optString("category")
        if (category.isEmpty()) return null
        val latest = progress.optJSONObject("latest_item")?.let {
            LatestItem(
                category = it.optString("category"),
                count = it.optInt("count"),
                id = it.optString("id"),
                playlist = it.optString("playlist"),
                title = it.optString("title"),
                json = it.optString("json"),
                csv = it.optString("csv"),
                truncated = it.optBoolean("json_truncated"),
                checkpoint = it.optBoolean("checkpoint"),
            )
        }
        return Triple(
            category,
            CategoryStatus(
                "Working",
                progress.optInt("count"),
                progress.optString("message"),
                if (progress.has("total") && !progress.isNull("total")) progress.optInt("total") else null,
            ),
            latest,
        )
    }
}

private data class PublishResult(val uris: List<Uri>, val error: String?)

private object DownloadPublisher {
    private val fileNames = listOf(
        "likes.json",
        "likes.csv",
        "playlists.json",
        "playlists.csv",
        "playlist_tracks.json",
        "playlist_tracks.csv",
        "report.json",
    )

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
    for (name in listOf("likes", "playlists", "playlist_tracks", "followings")) {
        val category = source.optJSONObject(name) ?: continue
        result[name] = CategoryStatus(
            status = category.optString("status", "Waiting"),
            count = category.optInt("count"),
            detail = category.optString("error").ifEmpty { category.optString("reason") },
            total = if (category.has("total") && !category.isNull("total")) category.optInt("total") else null,
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
    var confirmDeleteSnapshots by rememberSaveable { mutableStateOf(false) }
    val normalizedInput = try {
        normalizeProfileUrl(profileUrl)
    } catch (_: IllegalArgumentException) {
        ""
    }
    val profileHistoryLoaded = normalizedInput.isNotEmpty() && normalizedInput == state.profileUrl
    LaunchedEffect(profileUrl) {
        if (profileUrl.isNotBlank()) {
            delay(450)
            model.loadSnapshots(profileUrl)
        }
    }
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
                                Text("SoundCloud snapshot tool", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
                            "Keep a snapshot of what you love.",
                            style = MaterialTheme.typography.headlineMedium,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            "Save public likes, playlists, and their track IDs as local CSV and JSON. No login or audio downloads.",
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }

                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        OutlinedTextField(
                            value = profileUrl,
                            onValueChange = {
                                profileUrl = it
                                confirmRefetch = false
                                confirmDeleteSnapshots = false
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
                            enabled = !state.running && !state.snapshotHistoryLoading,
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
                                Text("Creating snapshot…")
                            } else {
                                Text("Create snapshot or resume")
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
                        Text("Snapshot progress", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                        val progressCategories = state.categories.values.filter { it.status != "unsupported" }
                        val requiredCategories = listOf("likes", "playlists", "playlist_tracks")
                        val hasKnownTotals = requiredCategories.all { name ->
                            state.categories[name]?.total?.let { it >= 0 } == true
                        }
                        if (state.running && hasKnownTotals) {
                            val total = progressCategories.sumOf { it.total ?: 0 }
                            val count = progressCategories.sumOf { minOf(it.count, it.total ?: it.count) }
                            val fraction = if (total == 0) 1f else (count.toFloat() / total).coerceIn(0f, 1f)
                            LinearProgressIndicator(
                                progress = { fraction },
                                modifier = Modifier.fillMaxWidth(),
                                color = MaterialTheme.colorScheme.primary,
                                trackColor = MaterialTheme.colorScheme.surfaceVariant,
                            )
                        } else if (state.running) {
                            LinearProgressIndicator(
                                modifier = Modifier.fillMaxWidth(),
                                color = MaterialTheme.colorScheme.primary,
                                trackColor = MaterialTheme.colorScheme.surfaceVariant,
                            )
                        } else if (requiredCategories.all {
                                state.categories[it]?.status == "complete"
                            }) {
                            LinearProgressIndicator(
                                progress = { 1f },
                                modifier = Modifier.fillMaxWidth(),
                                color = MaterialTheme.colorScheme.primary,
                                trackColor = MaterialTheme.colorScheme.surfaceVariant,
                            )
                        } else {
                            LinearProgressIndicator(
                                progress = { 0f },
                                modifier = Modifier.fillMaxWidth(),
                                color = MaterialTheme.colorScheme.primary,
                                trackColor = MaterialTheme.colorScheme.surfaceVariant,
                            )
                        }
                        Text(state.status, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (wide) {
                            Row(horizontalArrangement = Arrangement.spacedBy(28.dp)) {
                                CategoryLine("Likes", state.categories["likes"], Modifier.weight(1f))
                                CategoryLine("Playlists", state.categories["playlists"], Modifier.weight(1f))
                                CategoryLine("Playlist tracks", state.categories["playlist_tracks"], Modifier.weight(1f))
                            }
                        } else {
                            CategoryLine("Likes", state.categories["likes"], Modifier.fillMaxWidth())
                            CategoryLine("Playlists", state.categories["playlists"], Modifier.fillMaxWidth())
                            CategoryLine("Playlist tracks", state.categories["playlist_tracks"], Modifier.fillMaxWidth())
                        }
                        Text(
                            "Following and follower lists are not supported.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }

                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Live track IDs · ${state.trackIds.size}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        Text(
                            "Liked tracks and tracks found inside public playlists.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Surface(
                            modifier = Modifier.fillMaxWidth().height(250.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant,
                            shape = MaterialTheme.shapes.small,
                        ) {
                            if (state.trackIds.isEmpty()) {
                                androidx.compose.foundation.layout.Box(
                                    modifier = Modifier.fillMaxSize().padding(16.dp),
                                    contentAlignment = Alignment.CenterStart,
                                ) {
                                    Text(
                                        "Track IDs will appear as they are found.",
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        style = MaterialTheme.typography.bodySmall,
                                    )
                                }
                            } else {
                                LazyColumn(Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
                                    itemsIndexed(
                                        state.trackIds,
                                        key = { index, item -> "$index:${item.category}:${item.id}" },
                                    ) { _, item ->
                                        Row(
                                            modifier = Modifier.fillMaxWidth().heightIn(min = 40.dp),
                                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                                            verticalAlignment = Alignment.CenterVertically,
                                        ) {
                                            Text(
                                                if (item.category == "playlist_tracks") "PLAYLIST" else "LIKE",
                                                style = MaterialTheme.typography.labelSmall,
                                                color = MaterialTheme.colorScheme.primary,
                                            )
                                            Text(
                                                item.id,
                                                style = MaterialTheme.typography.bodySmall,
                                                color = MaterialTheme.colorScheme.onSurface,
                                            )
                                        }
                                        Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.25f))
                                    }
                                }
                            }
                        }
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
                    if (profileHistoryLoaded) {
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(
                                if (state.snapshotHistoryLoading) "Loading snapshot history…"
                                else "Snapshot history · ${state.snapshotCount}",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.SemiBold,
                            )
                            TextButton(
                                onClick = model::compareSnapshots,
                                enabled = state.snapshotCount >= 2 && !state.running && !state.snapshotHistoryLoading,
                                modifier = Modifier.heightIn(min = 48.dp),
                            ) {
                                Text("Compare latest two snapshots")
                            }
                            TextButton(
                                onClick = { confirmDeleteSnapshots = true },
                                enabled = state.snapshotCount > 0 && !state.running && !state.snapshotHistoryLoading,
                                modifier = Modifier.heightIn(min = 48.dp),
                            ) {
                                Text("Clear snapshot history")
                            }
                            state.snapshotComparison?.let {
                                Text(
                                    it,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                    if (!state.running && !state.snapshotHistoryLoading && profileHistoryLoaded) {
                        TextButton(onClick = { confirmRefetch = true }, modifier = Modifier.heightIn(min = 48.dp)) {
                            Text("Start over and replace saved files")
                        }
                    }

                    Divider(color = MaterialTheme.colorScheme.outline.copy(alpha = 0.45f))
                    Text(
                        "Only publicly visible metadata is saved. CloudSnatch does not add analytics or send your snapshots to a CloudSnatch server. SoundCloud requests are made directly from your device; public results are not guaranteed complete.",
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
            text = { Text("This replaces the current likes, playlist, and track files for this profile. Previously created snapshots remain available for comparison.") },
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

    if (confirmDeleteSnapshots) {
        AlertDialog(
            onDismissRequest = { confirmDeleteSnapshots = false },
            title = { Text("Clear saved snapshot history?") },
            text = { Text("This removes past snapshots for this profile but keeps the current exported files.") },
            confirmButton = {
                TextButton(onClick = {
                    confirmDeleteSnapshots = false
                    model.deleteSnapshots()
                }) { Text("Clear history") }
            },
            dismissButton = {
                TextButton(onClick = { confirmDeleteSnapshots = false }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun CategoryLine(name: String, item: CategoryStatus?, modifier: Modifier) {
    Column(modifier.padding(vertical = 4.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        val status = item?.status ?: "Waiting"
        val count = item?.count?.let {
            " · $it${item.total?.let { total -> " / $total" }.orEmpty()} items"
        }.orEmpty()
        Text(
            text = "$status$count${item?.detail?.let { " · $it" }.orEmpty()}",
            style = MaterialTheme.typography.bodySmall,
            color = if (status == "failed") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 4,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            when (name) {
                "Likes" -> "likes.json · likes.csv"
                "Playlists" -> "playlists.json · playlists.csv"
                else -> "playlist_tracks.json · playlist_tracks.csv"
            },
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
                "${item.category} · item ${item.count} · ${if (item.checkpoint) "snapshot checkpoint saved" else "JSON checkpoint pending"}",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(item.title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            if (item.id.isNotEmpty()) {
                Text(
                    "Track ID ${item.id}${item.playlist.takeIf(String::isNotEmpty)?.let { " · $it" }.orEmpty()}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
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
