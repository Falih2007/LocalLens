package app.locallens.companion

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.math.BigInteger
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.MessageDigest
import java.security.spec.ECGenParameterSpec
import java.util.Date
import javax.net.ssl.SSLContext
import javax.security.auth.x500.X500Principal

/** Android owns the non-exportable TLS key. Trust pins this certificate, never an IP/name. */
class Identity {
    private val alias = "locallens-tls-ec-v3"
    private val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
    init {
        if (!store.containsAlias(alias)) {
            val generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore")
            generator.initialize(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY)
                // TLS hashes its handshake transcript itself, then asks Keystore to sign that digest.
                // DIGEST_NONE authorizes that operation; it does not disable TLS hashing or certificate checks.
                .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
                .setDigests(KeyProperties.DIGEST_NONE, KeyProperties.DIGEST_SHA256)
                .setCertificateSubject(X500Principal("CN=LocalLens companion"))
                .setCertificateSerialNumber(BigInteger.valueOf(System.currentTimeMillis()))
                .setCertificateNotBefore(Date(System.currentTimeMillis()-86400000))
                .setCertificateNotAfter(Date(System.currentTimeMillis()+10L*365*86400000)).build())
            generator.generateKeyPair()
        }
    }
    val fingerprint: String get() = hash(store.getCertificate(alias).encoded)
    fun context(): SSLContext {
        // Expose only the corrected identity; an older unusable key may still exist after an upgrade.
        val key = store.getKey(alias, null) as java.security.PrivateKey
        val chain = store.getCertificateChain(alias).map { it as java.security.cert.X509Certificate }.toTypedArray()
        val keyManager = IdentityKeyManager(alias, key, chain)
        return SSLContext.getInstance("TLS").apply { init(arrayOf(keyManager), null, null) }
    }
    companion object {
        fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        fun tokenHash(token: String) = hash(token.toByteArray(Charsets.US_ASCII))
        fun verificationCode(fingerprint: String, token: String) = hash(("locallens-pair-v2\n"+fingerprint+"\n"+token).toByteArray(Charsets.US_ASCII))
            .take(16).uppercase().chunked(4).joinToString(" ")
    }
}
