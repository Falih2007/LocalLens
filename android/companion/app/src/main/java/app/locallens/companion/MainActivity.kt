package app.locallens.companion

import android.Manifest
import android.app.*
import android.content.*
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.*
import android.view.View
import android.widget.*

/** Native controls, no WebView, no terminal, no cloud dependency. */
class MainActivity : Activity() {
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var content: LinearLayout
    private var dialog: AlertDialog? = null
    private var shown: String? = null
    private var signature = ""
    private val tick = object : Runnable {
        override fun run() { refresh(); handler.postDelayed(this, 1000) }
    }
    private fun dp(value: Int) = (value*resources.displayMetrics.density).toInt()
    private val dark get() = resources.configuration.uiMode and 0x30 == 0x20
    private val foreground get() = if (dark) Color.rgb(245,245,247) else Color.rgb(29,29,31)
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        window.statusBarColor = if (dark) Color.rgb(18,18,20) else Color.rgb(246,247,249)
        window.navigationBarColor = window.statusBarColor
        val scroll = ScrollView(this).apply { setBackgroundColor(window.statusBarColor); isFillViewport = true }
        content = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(24), dp(48), dp(24), dp(32)) }
        scroll.addView(content); setContentView(scroll)
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED)
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
    }
    override fun onResume() { super.onResume(); signature = ""; handler.post(tick) }
    override fun onPause() { handler.removeCallbacks(tick); dialog?.dismiss(); dialog = null; shown = null; super.onPause() }
    private fun text(value: String, size: Float = 15f, bold: Boolean = false, parent: LinearLayout = content): TextView {
        return TextView(this).apply {
            text = value; textSize = size; setTextColor(this@MainActivity.foreground); setLineSpacing(dp(3).toFloat(), 1f)
            if (bold) typeface = Typeface.create("sans-serif", Typeface.BOLD)
            setPadding(0, dp(5), 0, dp(10)); parent.addView(this)
        }
    }
    private fun card(): LinearLayout = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL; setPadding(dp(20), dp(16), dp(20), dp(16))
        background = GradientDrawable().apply { setColor(if (dark) Color.rgb(30,30,32) else Color.WHITE); cornerRadius = dp(18).toFloat() }
        content.addView(this, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(18) })
    }
    private fun button(label: String, parent: LinearLayout, enabled: Boolean = true, action: () -> Unit) {
        parent.addView(Button(this).apply { text = label; isAllCaps = false; isEnabled = enabled; setOnClickListener {
            runCatching { action() }.onFailure { Toast.makeText(this@MainActivity, it.message ?: "Action could not be completed.", Toast.LENGTH_LONG).show() }
            signature = ""; refresh()
        } }, LinearLayout.LayoutParams(-1,-2))
    }
    private fun refresh() {
        val service = CompanionService.current
        val requests = runCatching { service?.pairing?.requests() }.getOrNull() ?: emptyList()
        val devices = runCatching { service?.pairing?.devices() }.getOrNull() ?: emptyList()
        val state = runCatching { service?.status() }.getOrNull()
        val next = "${service?.message}|${service?.endpoint}|${devices}|${state?.optDouble("available_gib")?.times(10)?.toInt()}|${requests.map { it.id }}"
        if (next != signature) {
            signature = next; content.removeAllViews()
            text("LOCALLENS COMPANION", 12f, true)
            text("Your devices.\nWorking together.", 32f, true)
            text("Connect privately on your Wi-Fi. You decide which computers to trust.")
            val discovery = card()
            text(if (service == null) "Ready when you are." else if (service.discoveryEnabled) "Discoverable nearby" else "Checking secure connection", 20f, true, discovery)
            text(service?.message ?: "Enable discovery, then choose Add Device on your laptop.", parent = discovery)
            if (service?.tlsReady == true) text(service.tlsCheck, 12f, parent = discovery)
            button(if (service == null) "Enable discovery" else "Stop discovery & disconnect", discovery) {
                if (service == null) startForegroundService(Intent(this, CompanionService::class.java))
                else stopService(Intent(this, CompanionService::class.java))
            }
            if (service != null && state != null) {
                val resources = card()
                text(service.name, 20f, true, resources)
                text("${state.optString("os")} · ${state.optString("cpu")}", parent = resources)
                text("%.1f GiB physical · %.1f GiB available".format(state.optDouble("physical_ram_gib"), state.optDouble("available_gib")), parent = resources)
                text("Battery ${state.opt("battery_percent")}% · ${state.opt("battery_temperature_c")}°C", parent = resources)
                text("Compute sharing unavailable", 17f, true, resources)
                text(service.worker.reason, parent = resources)
                button("Start compute sharing", resources, false) {}
                val trust = card()
                text("Trusted computers", 20f, true, trust)
                if (devices.isEmpty()) text("None yet. First-time connections always need your approval.", parent = trust)
                devices.forEach { (hash, name, online) ->
                    text("$name · ${if (online) "Connected" else "Offline / disconnected"}", bold = true, parent = trust)
                    button("Revoke $name", trust) { service.pairing.revoke(hash) }
                }
                val verification = card()
                text("Phone identity", 17f, true, verification)
                text("Each pairing request shows its own verification code. You can also compare this full certificate fingerprint with Windows.", parent = verification)
                text(service.identity.fingerprint.chunked(8).joinToString(" "), 12f, parent = verification).setTextIsSelectable(true)
                text("Advanced connection address: ${service.endpoint}", 12f, parent = verification)
            }
            text("Keep this app open for first-time pairing. Android may stop background activity; reopen LocalLens if your laptop loses contact.", 12f)
            text("LocalLens ${packageManager.getPackageInfo(packageName, 0).versionName}", 12f)
        }
        if (shown != null && requests.none { it.id == shown }) { dialog?.dismiss(); dialog = null; shown = null }
        if (dialog == null && requests.isNotEmpty() && service != null) {
            val request = requests.first(); shown = request.id
            dialog = AlertDialog.Builder(this).setTitle("Pair with ${request.name}?")
                .setMessage("Verify the same code on your laptop:\n\n${request.code}\n\nRequested from ${request.host}. Only approve your own computer. Compute sharing stays off.")
                .setPositiveButton("Codes match · Approve") { _, _ ->
                    runCatching { service.pairing.approve(request.id) }.onFailure { Toast.makeText(this, it.message, Toast.LENGTH_LONG).show() }
                    dialog = null; shown = null; signature = ""
                }.setNegativeButton("Reject") { _, _ -> service.pairing.reject(request.id); dialog = null; shown = null }
                .setOnCancelListener { service.pairing.reject(request.id); dialog = null; shown = null }.create()
            dialog?.show()
        }
    }
}
