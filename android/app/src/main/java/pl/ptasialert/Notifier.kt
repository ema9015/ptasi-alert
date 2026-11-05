package pl.ptasialert

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import org.json.JSONObject

object Notifier {
    private const val CHANNEL = "ogniska"

    fun createChannel(ctx: Context) {
        if (Build.VERSION.SDK_INT >= 26) {
            val ch = NotificationChannel(CHANNEL, ctx.getString(R.string.channel_name), NotificationManager.IMPORTANCE_HIGH)
            ch.description = ctx.getString(R.string.channel_desc)
            ctx.getSystemService(NotificationManager::class.java).createNotificationChannel(ch)
        }
    }

    fun allowed(ctx: Context): Boolean {
        if (Build.VERSION.SDK_INT >= 33 &&
            ctx.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return false
        return NotificationManagerCompat.from(ctx).areNotificationsEnabled()
    }

    private fun title(e: JSONObject): String {
        val ch = e.optString("choroba")
        val name = when {
            e.optString("rodzaj") == "komunikat" -> "Komunikat: " + e.optString("tytul_zrodla").take(80)
            e.optString("typ") == "ptaki dzikie" -> "Grypa ptaków u dzikich ptaków"
            ch == "ND" -> "Nowe ognisko rzekomego pomoru drobiu"
            ch == "LPAI" -> "Nowe ognisko nisko zjadliwej grypy ptaków"
            else -> "Nowe ognisko grypy ptaków"
        }
        return if (e.optString("potwierdzenie") == "media") "$name (niepotwierdzone)" else name
    }

    private fun place(e: JSONObject): String {
        val parts = ArrayList<String>()
        fun add(prefix: String, key: String) {
            val v = e.optString(key)
            if (v.isNotEmpty() && v != "null") parts.add(prefix + v)
        }
        add("", "miejscowosc")
        if (e.optString("gmina") != e.optString("miejscowosc")) add("gm. ", "gmina")
        add("pow. ", "powiat")
        add("woj. ", "woj")
        return parts.joinToString(", ").ifEmpty { "Polska" }
    }

    private fun details(e: JSONObject): String {
        val sb = StringBuilder(place(e))
        val ptaki = e.optString("ptaki")
        if (ptaki.isNotEmpty() && ptaki != "null") sb.append("\n").append(ptaki)
        if (e.has("liczba") && !e.isNull("liczba")) sb.append(", ").append(e.optLong("liczba")).append(" szt.")
        sb.append("\nStrefy: min. 3 km (zapowietrzona) i 10 km (zagrożona). Dotknij, aby zobaczyć na mapie.")
        return sb.toString()
    }

    private fun openIntent(ctx: Context, id: String?, code: Int): PendingIntent {
        val i = Intent(ctx, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        if (id != null) i.putExtra(MainActivity.EXTRA_ID, id)
        return PendingIntent.getActivity(ctx, code, i, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    @SuppressLint("MissingPermission")
    fun notifyEvents(ctx: Context, list: List<JSONObject>) {
        if (list.isEmpty() || !allowed(ctx)) return
        createChannel(ctx)
        val nm = NotificationManagerCompat.from(ctx)
        for (e in list.take(5)) {
            val id = e.optString("id")
            val n = NotificationCompat.Builder(ctx, CHANNEL)
                .setSmallIcon(R.drawable.ic_stat)
                .setColor(0xFFC2302E.toInt())
                .setContentTitle(title(e))
                .setContentText(place(e))
                .setStyle(NotificationCompat.BigTextStyle().bigText(details(e)))
                .setContentIntent(openIntent(ctx, id, id.hashCode()))
                .setAutoCancel(true)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setCategory(NotificationCompat.CATEGORY_ALARM)
                .build()
            nm.notify(id.hashCode(), n)
        }
        if (list.size > 5) {
            val n = NotificationCompat.Builder(ctx, CHANNEL)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle("Kolejne nowe zdarzenia: " + (list.size - 5))
                .setContentText("Otwórz aplikację, aby zobaczyć wszystkie.")
                .setContentIntent(openIntent(ctx, null, 999))
                .setAutoCancel(true)
                .build()
            nm.notify(999, n)
        }
    }

    @SuppressLint("MissingPermission")
    fun test(ctx: Context) {
        if (!allowed(ctx)) return
        createChannel(ctx)
        val n = NotificationCompat.Builder(ctx, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat)
            .setColor(0xFF0D6A5A.toInt())
            .setContentTitle("Ptasi Alert – powiadomienie testowe")
            .setContentText("Powiadomienia działają. Sprawdzanie co 15 minut.")
            .setContentIntent(openIntent(ctx, null, 998))
            .setAutoCancel(true)
            .build()
        NotificationManagerCompat.from(ctx).notify(998, n)
    }
}
