package pl.ptasialert

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient

/** Główny ekran: mapa i lista ognisk (strona Ptasi Alert w WebView) + most do ustawień powiadomień. */
class MainActivity : Activity() {

    private lateinit var web: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Notifier.createChannel(this)
        CheckWorker.schedule(this)

        web = WebView(this)
        setContentView(web)
        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        web.settings.userAgentString = web.settings.userAgentString + " PtasiAlertApp/" + BuildConfig.VERSION_NAME
        web.addJavascriptInterface(Bridge(this), "PtasiAlertApp")
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val url = request.url
                val site = Uri.parse(BuildConfig.SITE_URL)
                val inside = url.host == site.host && (url.path ?: "/").startsWith(site.path ?: "/")
                if (inside || url.scheme == "file") return false
                openExternal(url)
                return true
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (request.isForMainFrame) view.loadUrl("file:///android_asset/offline.html")
            }
        }

        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }

        if (savedInstanceState != null) web.restoreState(savedInstanceState) else web.loadUrl(startUrl(intent))
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        web.loadUrl(startUrl(intent))
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    fun reloadSite() {
        web.loadUrl(BuildConfig.SITE_URL)
    }

    private fun openExternal(url: Uri) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, url))
        } catch (e: ActivityNotFoundException) {
            // brak aplikacji do otwarcia linku – ignorujemy
        }
    }

    private fun startUrl(i: Intent?): String {
        val id = i?.getStringExtra(EXTRA_ID)
        return if (id.isNullOrEmpty()) BuildConfig.SITE_URL else BuildConfig.SITE_URL + "?e=" + Uri.encode(id)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (web.canGoBack()) web.goBack() else super.onBackPressed()
    }

    companion object {
        const val EXTRA_ID = "id"
    }
}
