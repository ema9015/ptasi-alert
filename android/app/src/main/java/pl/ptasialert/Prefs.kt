package pl.ptasialert

import android.content.Context
import org.json.JSONArray

/** Ustawienia zapisane w telefonie. */
object Prefs {
    private fun sp(ctx: Context) = ctx.getSharedPreferences("ptasi_alert", Context.MODE_PRIVATE)

    fun wojJson(ctx: Context): String = sp(ctx).getString("woj", "[]") ?: "[]"
    fun setWojJson(ctx: Context, json: String) {
        val clean = try { JSONArray(json).toString() } catch (e: Exception) { "[]" }
        sp(ctx).edit().putString("woj", clean).apply()
    }

    fun wojList(ctx: Context): Set<String> {
        val arr = try { JSONArray(wojJson(ctx)) } catch (e: Exception) { JSONArray() }
        return (0 until arr.length()).map { arr.optString(it) }.filter { it.isNotEmpty() }.toSet()
    }

    fun notifyOn(ctx: Context) = sp(ctx).getBoolean("notify", true)
    fun setNotifyOn(ctx: Context, on: Boolean) = sp(ctx).edit().putBoolean("notify", on).apply()

    fun mediaOn(ctx: Context) = sp(ctx).getBoolean("media", true)
    fun setMediaOn(ctx: Context, on: Boolean) = sp(ctx).edit().putBoolean("media", on).apply()

    fun seen(ctx: Context): Set<String> = sp(ctx).getStringSet("seen", emptySet()) ?: emptySet()
    fun setSeen(ctx: Context, ids: Set<String>) = sp(ctx).edit().putStringSet("seen", HashSet(ids)).apply()

    fun initialized(ctx: Context) = sp(ctx).getBoolean("init", false)
    fun setInitialized(ctx: Context) = sp(ctx).edit().putBoolean("init", true).apply()
}
