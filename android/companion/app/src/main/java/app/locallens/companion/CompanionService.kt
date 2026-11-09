package app.locallens.companion

import android.app.*
import android.content.*
import android.content.pm.ServiceInfo
import android.net.*
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.*
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.*
import java.util.concurrent.*
import javax.net.ssl.SSLServerSocket
import javax.net.ssl.SSLSocket

class CompanionService : Service() {
    companion object { @Volatile var current: CompanionService? = null }
    lateinit var identity: Identity; private set
    lateinit var pairing: PairingState; private set
    val worker = WorkerController()
    @Volatile var message = "Starting secure companion…"
    @Volatile var endpoint = ""
    @Volatile var discoveryEnabled = false
    @Volatile var tlsReady = false
    @Volatile var tlsCheck = "Checking the phone's secure connection…"
    private var listener: SSLServerSocket? = null
    private var registration: NsdManager.RegistrationListener? = null
    private var address: String? = null
    private val scheduler = Executors.newSingleThreadScheduledExecutor()
    private val connections = ConcurrentHashMap.newKeySet<SSLSocket>()
    private val pool = ThreadPoolExecutor(4, 8, 30, TimeUnit.SECONDS, ArrayBlockingQueue(16))
    private val main = Handler(Looper.getMainLooper())
    private val network by lazy { getSystemService(ConnectivityManager::class.java) }
    private val nsd by lazy { getSystemService(NsdManager::class.java) }
    val name: String get() = "${Build.MANUFACTURER} ${Build.MODEL}".trim().take(80)
    private val callback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) { scheduleNetwork() }
        override fun onLost(network: Network) { scheduleNetwork() }
        override fun onLinkPropertiesChanged(network: Network, properties: LinkProperties) { scheduleNetwork() }
    }
    override fun onBind(intent: Intent?) = null
    override fun onCreate() {
        super.onCreate()
        val notifications = getSystemService(NotificationManager::class.java)
        notifications.createNotificationChannel(NotificationChannel("devices", "Device connections", NotificationManager.IMPORTANCE_DEFAULT))
        val notification = notification("Discovery is starting. Tap to manage devices.")
        if (Build.VERSION.SDK_INT >= 29) startForeground(1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
        else startForeground(1, notification)
        current = this
        scheduler.execute {
            try {
                message = tlsCheck
                identity = Identity(); pairing = PairingState(this)
                val protocols = TlsPreflight.run(identity.context(), identity.fingerprint)
                if (current !== this) return@execute
                tlsCheck = "TLS self-check passed · ${protocols.joinToString()}"
                tlsReady = true; discoveryEnabled = true
                network.registerNetworkCallback(NetworkRequest.Builder().addTransportType(NetworkCapabilities.TRANSPORT_WIFI).build(), callback)
                scheduler.scheduleWithFixedDelay({ runCatching { updateNetwork(); pairing.expire() }.onFailure { message = it.message ?: "Network unavailable." } }, 0, 5, TimeUnit.SECONDS)
            } catch (e: Exception) {
                tlsCheck = "TLS self-check failed: ${e.message}"; message = tlsCheck
                android.util.Log.w("LocalLensTLS", "TLS preflight failed", e)
            }
        }
    }
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == "stop") stopSelf()
        return START_NOT_STICKY // User must reopen/enable after Android stops the service.
    }
    private fun notification(text: String): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val stop = PendingIntent.getService(this, 1, Intent(this, CompanionService::class.java).setAction("stop"), PendingIntent.FLAG_IMMUTABLE)
        return Notification.Builder(this, "devices").setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle("LocalLens companion").setContentText(text).setContentIntent(open).setOngoing(true)
            .addAction(Notification.Action.Builder(null, "Stop discovery", stop).build()).build()
    }
    private fun scheduleNetwork() { if (!scheduler.isShutdown) runCatching { scheduler.execute { runCatching { updateNetwork() } } } }
    @Synchronized private fun updateNetwork() {
        if (!discoveryEnabled) return
        val host = network.allNetworks.firstNotNullOfOrNull { item ->
            if (network.getNetworkCapabilities(item)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) != true) null
            else network.getLinkProperties(item)?.linkAddresses?.map { it.address }?.firstOrNull { it is Inet4Address && privateAddress(it) }?.hostAddress
        }
        if (host == address && listener != null) return
        closeNetwork()
        if (host == null) { message = "Connect to a private Wi-Fi network, then keep discovery enabled."; return }
        address = host
        val server = identity.context().serverSocketFactory.createServerSocket(0, 16, InetAddress.getByName(host)) as SSLServerSocket
        server.enabledProtocols = server.supportedProtocols.filter { it == "TLSv1.2" || it == "TLSv1.3" }.toTypedArray()
        listener = server; endpoint = "$host:${server.localPort}"
        val info = NsdServiceInfo().apply {
            serviceName = "LocalLens-${identity.fingerprint.take(12)}"; serviceType = "_locallens._tcp."; port = server.localPort
            setAttribute("name", name); setAttribute("platform", "Android ${Build.VERSION.RELEASE}")
            setAttribute("fingerprint", identity.fingerprint); setAttribute("protocol", "locallens-companion/2")
        }
        val registrationListener = object : NsdManager.RegistrationListener {
            override fun onServiceRegistered(info: NsdServiceInfo) { message = "Discoverable on Wi-Fi · encrypted pairing ready" }
            override fun onRegistrationFailed(info: NsdServiceInfo, code: Int) { message = "mDNS registration failed ($code). Advanced address: $endpoint" }
            override fun onServiceUnregistered(info: NsdServiceInfo) = Unit
            override fun onUnregistrationFailed(info: NsdServiceInfo, code: Int) = Unit
        }
        registration = registrationListener
        main.post { runCatching { nsd.registerService(info, NsdManager.PROTOCOL_DNS_SD, registrationListener) }.onFailure { message = "Discovery unavailable: ${it.message}" } }
        Thread({
            while (!server.isClosed) {
                try {
                    val socket = server.accept() as SSLSocket
                    if (!privateAddress(socket.inetAddress)) { socket.close(); continue }
                    socket.soTimeout = 8000; connections.add(socket)
                    try { pool.execute { handle(socket) } } catch (_: RejectedExecutionException) { connections.remove(socket); socket.close() }
                } catch (_: Exception) { if (!server.isClosed) message = "Connection listener interrupted." }
            }
        }, "locallens-tls").apply { isDaemon = true; start() }
    }
    private fun privateAddress(address: InetAddress): Boolean {
        if (address !is Inet4Address) return false
        val b = address.address.map { it.toInt() and 255 }
        return b[0] == 10 || b[0] == 192 && b[1] == 168 || b[0] == 172 && b[1] in 16..31
    }
    private fun handle(socket: SSLSocket) {
        socket.use {
            try {
                try { socket.startHandshake() } catch (e: Exception) {
                    message = "Secure handshake failed: ${e.javaClass.simpleName}: ${e.message}"
                    android.util.Log.w("LocalLensTLS", "TLS handshake failed", e)
                    return
                }
                val input = socket.inputStream
                val headers = ByteArrayOutputStream()
                while (headers.size() < 8192) {
                    val char = input.read(); require(char >= 0) { "Incomplete request." }; headers.write(char)
                    val bytes = headers.toByteArray()
                    if (bytes.size >= 4 && bytes.takeLast(4) == listOf<Byte>(13, 10, 13, 10)) break
                }
                val lines = headers.toString("US-ASCII").split("\r\n")
                val request = lines.first().split(" ")
                require(request.size == 3 && request[0] == "POST") { "POST required." }
                val fields = mutableMapOf<String, String>()
                lines.drop(1).filter { it.contains(':') }.forEach { line ->
                    val key = line.substringBefore(':').lowercase()
                    require(key !in fields) { "Duplicate header." }; fields[key] = line.substringAfter(':').trim()
                }
                require("transfer-encoding" !in fields) { "Unsupported transfer encoding." }
                val size = fields["content-length"]?.toIntOrNull() ?: 0
                require(size in 0..65536) { "Request too large." }
                val bytes = ByteArray(size); var count = 0
                while (count < size) { val n = input.read(bytes, count, size-count); require(n > 0) { "Incomplete body." }; count += n }
                val body = if (size == 0) JSONObject() else JSONObject(String(bytes, Charsets.UTF_8))
                val token = fields["authorization"]?.removePrefix("Bearer ") ?: ""
                val result: JSONObject
                when (request[1]) {
                    "/identity" -> result = JSONObject().put("name", name).put("protocol", "locallens-companion/2")
                    "/pair" -> {
                        val pending = pairing.request(body.optString("token"), body.optString("name", "Computer"), socket.inetAddress.hostAddress ?: "", identity.fingerprint)
                        getSystemService(NotificationManager::class.java).notify(2, notification("${pending.name} requests pairing. Tap to compare the verification code."))
                        result = JSONObject().put("status", "pending").put("request_id", pending.id)
                    }
                    "/pair/status" -> result = JSONObject().put("status", pairing.status(token))
                    else -> {
                        val hash = try { pairing.authorize(token) } catch (_: IllegalArgumentException) { reply(socket, 403, JSONObject().put("error", "Phone approval required.")); return }
                        when (request[1]) {
                            "/status" -> result = status()
                            "/echo" -> result = JSONObject().put("echo", body.opt("echo"))
                            "/revoke" -> { pairing.revoke(hash); result = JSONObject().put("status", "revoked") }
                            "/session/close" -> { pairing.disconnect(hash); worker.stop(); result = JSONObject().put("status", "disconnected") }
                            "/sharing" -> { require(body.opt("enabled") == false) { "Enable sharing on the phone." }; worker.stop(); result = JSONObject().put("status", "disabled") }
                            "/rpc" -> { reply(socket, 409, JSONObject().put("error", worker.reason)); return }
                            else -> { reply(socket, 404, JSONObject().put("error", "Operation not supported.")); return }
                        }
                    }
                }
                reply(socket, 200, result)
            } catch (e: Exception) { runCatching { reply(socket, 400, JSONObject().put("error", e.message ?: "Request failed.")) } }
            finally { connections.remove(socket) }
        }
    }
    private fun reply(socket: SSLSocket, code: Int, result: JSONObject) {
        val body = result.toString().toByteArray(Charsets.UTF_8)
        val output = socket.outputStream
        output.write("HTTP/1.1 $code ${if (code == 200) "OK" else "Rejected"}\r\nContent-Type: application/json\r\nContent-Length: ${body.size}\r\nConnection: close\r\n\r\n".toByteArray(Charsets.US_ASCII))
        output.write(body); output.flush()
    }
    fun status(): JSONObject {
        check(tlsReady) { "Secure connection checks have not passed." }
        val memory = ActivityManager.MemoryInfo().also { getSystemService(ActivityManager::class.java).getMemoryInfo(it) }
        val battery = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = battery?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = battery?.getIntExtra(BatteryManager.EXTRA_SCALE, 100) ?: 100
        val temperature = (battery?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0) ?: 0)/10.0
        val thermal = if (Build.VERSION.SDK_INT >= 29) getSystemService(PowerManager::class.java).currentThermalStatus else -1
        return JSONObject().put("name", name).put("device_type", "phone").put("os", "Android ${Build.VERSION.RELEASE}")
            .put("cpu", if (Build.VERSION.SDK_INT >= 31) Build.SOC_MODEL else Build.HARDWARE)
            .put("gpu", "Not probed").put("npu", "Not probed").put("physical_ram_gib", memory.totalMem/1073741824.0)
            .put("available_gib", memory.availMem/1073741824.0).put("swap_gib", JSONObject.NULL)
            .put("battery_percent", if (level >= 0 && scale > 0) 100*level/scale else JSONObject.NULL)
            .put("battery_temperature_c", temperature).put("thermal_status", thermal).put("low_memory", memory.lowMemory)
            .put("sharing_enabled", false).put("runtime", worker.runtime()).put("inference_participation", "unverified")
    }
    @Synchronized private fun closeNetwork() {
        listener?.close(); listener = null
        connections.forEach { runCatching { it.close() } }; connections.clear()
        registration?.let { previous -> main.post { runCatching { nsd.unregisterService(previous) } } }
        registration = null; address = null; endpoint = ""; worker.stop()
    }
    override fun onDestroy() {
        discoveryEnabled = false; current = null
        runCatching { network.unregisterNetworkCallback(callback) }
        scheduler.shutdownNow(); closeNetwork(); pool.shutdownNow()
        getSystemService(NotificationManager::class.java).cancel(2)
        super.onDestroy()
    }
}
