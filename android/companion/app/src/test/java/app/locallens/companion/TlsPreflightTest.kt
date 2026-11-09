package app.locallens.companion

import java.nio.file.Files
import java.nio.file.Path
import java.security.KeyStore
import java.security.PrivateKey
import java.security.cert.X509Certificate
import javax.net.ssl.SSLContext
import org.junit.Assert.*
import org.junit.BeforeClass
import org.junit.Test

/** Real JVM TLS; test-only keys are generated at runtime and never bundled in the APK. */
class TlsPreflightTest {
    companion object {
        lateinit var context: SSLContext
        lateinit var fingerprint: String
        lateinit var manager: IdentityKeyManager
        @BeforeClass @JvmStatic fun setup() {
            val folder = Files.createTempDirectory("locallens-tls-test")
            val file = folder.resolve("fixture.p12")
            try {
                val executable = Path.of(System.getProperty("java.home"), "bin", if (System.getProperty("os.name").startsWith("Windows")) "keytool.exe" else "keytool").toString()
                val process = ProcessBuilder(executable, "-genkeypair", "-alias", "fixture", "-keyalg", "EC", "-groupname", "secp256r1",
                    "-sigalg", "SHA256withECDSA", "-dname", "CN=LocalLens TLS test", "-validity", "1", "-storetype", "PKCS12",
                    "-keystore", file.toString(), "-storepass", "fixture-only-password", "-noprompt").redirectErrorStream(true).start()
                val output = process.inputStream.bufferedReader().readText()
                check(process.waitFor() == 0) { output }
                val store = KeyStore.getInstance("PKCS12").apply { Files.newInputStream(file).use { load(it, "fixture-only-password".toCharArray()) } }
                val key = store.getKey("fixture", "fixture-only-password".toCharArray()) as PrivateKey
                val chain = store.getCertificateChain("fixture").map { it as X509Certificate }.toTypedArray()
                manager = IdentityKeyManager("fixture", key, chain)
                fingerprint = Identity.hash(chain[0].encoded)
                context = SSLContext.getInstance("TLS").apply { init(arrayOf(manager), null, null) }
            } finally { Files.deleteIfExists(file); Files.deleteIfExists(folder) }
        }
    }
    @Test fun realTls12AndTls13HandshakeAndEncryptedExchange() {
        val protocols = TlsPreflight.run(context, fingerprint)
        assertTrue(protocols.contains("TLSv1.2")); assertTrue(protocols.contains("TLSv1.3"))
    }
    @Test fun wrongCertificatePinCannotPassPreflight() {
        try { TlsPreflight.run(context, "0".repeat(64)); fail("Incorrect pin was accepted") }
        catch (error: IllegalStateException) { assertNotNull(error.cause) }
    }
    @Test fun oldRsaAliasesAndUnknownKeysAreNeverSelected() {
        assertEquals("fixture", manager.chooseServerAlias("EC", null, null))
        assertNull(manager.chooseServerAlias("RSA", null, null))
        assertNull(manager.getPrivateKey("old-rsa")); assertNull(manager.getCertificateChain("old-rsa"))
    }
}
