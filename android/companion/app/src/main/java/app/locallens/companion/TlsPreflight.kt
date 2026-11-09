package app.locallens.companion

import java.net.InetAddress
import java.net.InetSocketAddress
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import java.util.concurrent.atomic.AtomicReference
import javax.net.ssl.*

/** Real loopback TLS with the actual server key. It is neither pairing nor an inference benchmark. */
object TlsPreflight {
    fun run(serverContext: SSLContext, fingerprint: String): List<String> {
        val protocols = serverContext.supportedSSLParameters.protocols.filter { it == "TLSv1.2" || it == "TLSv1.3" }
        check(protocols.isNotEmpty()) { "TLS 1.2 or newer is required." }
        protocols.forEach { protocol -> checkProtocol(serverContext, fingerprint, protocol) }
        return protocols
    }

    private fun checkProtocol(serverContext: SSLContext, fingerprint: String, protocol: String) {
        val loopback = InetAddress.getByName("127.0.0.1")
        val failure = AtomicReference<Throwable?>(null)
        val server = serverContext.serverSocketFactory.createServerSocket(0, 1, loopback) as SSLServerSocket
        server.enabledProtocols = arrayOf(protocol)
        server.soTimeout = 6000
        val thread = Thread({
            try {
                (server.accept() as SSLSocket).use { accepted ->
                    accepted.soTimeout = 5000
                    accepted.startHandshake()
                    check(accepted.inputStream.read() == 37) { "TLS self-check request did not match." }
                    accepted.outputStream.write(73); accepted.outputStream.flush()
                }
            } catch (error: Exception) { failure.set(error) }
        }, "locallens-tls-self-check").apply { isDaemon = true; start() }
        try {
            val trust = object : X509TrustManager {
                override fun getAcceptedIssuers() = emptyArray<X509Certificate>()
                override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) { throw CertificateException("Client authentication is not used in this check.") }
                override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {
                    if (chain.isNullOrEmpty() || Identity.hash(chain[0].encoded) != fingerprint) throw CertificateException("TLS self-check certificate pin mismatch.")
                }
            }
            val clientContext = SSLContext.getInstance("TLS").apply { init(null, arrayOf(trust), null) }
            (clientContext.socketFactory.createSocket() as SSLSocket).use { client ->
                client.enabledProtocols = arrayOf(protocol); client.soTimeout = 5000
                client.connect(InetSocketAddress(loopback, server.localPort), 5000)
                client.startHandshake()
                check(Identity.hash(client.session.peerCertificates[0].encoded) == fingerprint) { "Certificate pin mismatch." }
                client.outputStream.write(37); client.outputStream.flush()
                check(client.inputStream.read() == 73) { "TLS self-check response did not match." }
            }
            thread.join(6000)
            failure.get()?.let { throw IllegalStateException("$protocol server signing failed: ${it.message}", it) }
            check(!thread.isAlive) { "$protocol self-check timed out." }
        } catch (error: Exception) {
            throw IllegalStateException("$protocol: ${failure.get()?.message ?: error.message}", error)
        } finally { server.close(); thread.join(1000) }
    }
}
