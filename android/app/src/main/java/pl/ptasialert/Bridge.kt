package pl.ptasialert

import android.webkit.JavascriptInterface

/** Funkcje dostępne dla strony jako window.PtasiAlertApp. */
class Bridge(private val act: MainActivity) {

    @JavascriptInterface
    fun setWojewodztwa(json: String) = Prefs.setWojJson(act, json)

    @JavascriptInterface
    fun getWojewodztwa(): String = Prefs.wojJson(act)

    @JavascriptInterface
    fun isNotifyOn(): Boolean = Prefs.notifyOn(act)

    @JavascriptInterface
    fun setNotifyOn(on: Boolean) = Prefs.setNotifyOn(act, on)

    @JavascriptInterface
    fun isMediaOn(): Boolean = Prefs.mediaOn(act)

    @JavascriptInterface
    fun setMediaOn(on: Boolean) = Prefs.setMediaOn(act, on)

    @JavascriptInterface
    fun checkNow() = CheckWorker.runOnce(act)

    @JavascriptInterface
    fun testNotification() = Notifier.test(act)

    @JavascriptInterface
    fun notificationsAllowed(): Boolean = Notifier.allowed(act)

    @JavascriptInterface
    fun version(): String = BuildConfig.VERSION_NAME

    @JavascriptInterface
    fun reload() {
        act.runOnUiThread { act.reloadSite() }
    }
}
