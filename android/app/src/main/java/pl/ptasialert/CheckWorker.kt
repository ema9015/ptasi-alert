package pl.ptasialert

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit

/** Co 15 minut w tle pobiera dane i pokazuje powiadomienia o nowych ogniskach w wybranych województwach. */
class CheckWorker(ctx: Context, params: WorkerParameters) : Worker(ctx, params) {

    override fun doWork(): Result {
        val ctx = applicationContext
        return try {
            val conn = URL(BuildConfig.SITE_URL + "data/zdarzenia.json?t=" + System.currentTimeMillis())
                .openConnection() as HttpURLConnection
            conn.connectTimeout = 20000
            conn.readTimeout = 30000
            conn.setRequestProperty("User-Agent", "PtasiAlertApp/" + BuildConfig.VERSION_NAME)
            val text = try {
                conn.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            } finally {
                conn.disconnect()
            }
            val arr: JSONArray = JSONObject(text).optJSONArray("zdarzenia") ?: JSONArray()

            val seen = Prefs.seen(ctx)
            val firstTime = !Prefs.initialized(ctx)
            val woj = Prefs.wojList(ctx)
            val media = Prefs.mediaOn(ctx)
            val all = HashSet<String>()
            val fresh = ArrayList<JSONObject>()
            for (i in 0 until arr.length()) {
                val e = arr.optJSONObject(i) ?: continue
                val id = e.optString("id")
                if (id.isEmpty()) continue
                all.add(id)
                if (id in seen) continue
                if (e.optString("status") != "aktywne") continue
                if (!media && e.optString("potwierdzenie") == "media") continue
                val w = e.optString("woj")
                if (woj.isNotEmpty() && w !in woj && w != "cała Polska") continue
                fresh.add(e)
            }
            Prefs.setSeen(ctx, all)
            Prefs.setInitialized(ctx)
            if (!firstTime && Prefs.notifyOn(ctx)) Notifier.notifyEvents(ctx, fresh)
            Result.success()
        } catch (e: Exception) {
            Result.retry()
        }
    }

    companion object {
        private const val NAME = "sprawdzanie-ognisk"

        fun schedule(ctx: Context) {
            val req = PeriodicWorkRequestBuilder<CheckWorker>(15, TimeUnit.MINUTES)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            WorkManager.getInstance(ctx).enqueueUniquePeriodicWork(NAME, ExistingPeriodicWorkPolicy.KEEP, req)
        }

        fun runOnce(ctx: Context) {
            WorkManager.getInstance(ctx).enqueue(OneTimeWorkRequestBuilder<CheckWorker>().build())
        }
    }
}
