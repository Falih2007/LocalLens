package app.locallens.companion

import android.content.Context
import java.security.SecureRandom

data class PairRequest(val id: String, val hash: String, val name: String, val host: String, val created: Long, val code: String)

/** Only SHA-256 hashes of random 256-bit bearer secrets are persisted, in app-private storage.
 * No bearer secret is stored on Android. The TLS private key stays in Android Keystore. */
interface TrustRepository {
    fun load(): Map<String, String>
    fun save(records: Map<String, String>)
}

class PairingState(private val repository: TrustRepository, private val clock: () -> Long = { System.nanoTime()/1_000_000 }) {
    constructor(context: Context): this(AndroidTrustRepository(context))
    private val trusted = mutableMapOf<String, String>()
    private val pending = linkedMapOf<String, PairRequest>()
    private val attempts = mutableMapOf<String, MutableList<Long>>()
    private val seen = mutableMapOf<String, Long>()
    init {
        trusted.putAll(repository.load())
    }
    @Synchronized fun request(token: String, name: String, host: String, fingerprint: String): PairRequest {
        require(Regex("[a-f0-9]{64}").matches(token)) { "Invalid pairing credential." }
        require(Regex("[a-f0-9]{64}").matches(fingerprint)) { "Invalid certificate identity." }
        expire()
        val now = clock()
        attempts.entries.removeAll { entry -> entry.value.all { now-it > 60000 } }
        require(host in attempts || attempts.size < 256) { "Pairing is busy. Try again shortly." }
        val recent = attempts.getOrPut(host) { mutableListOf() }.apply { removeAll { now-it > 60000 } }
        require(recent.size < 5) { "Too many requests. Wait one minute." }
        recent.add(now)
        require(pending.size < 8) { "Too many pending requests." }
        val hash = Identity.tokenHash(token)
        require(hash !in trusted && pending.values.none { it.hash == hash }) { "Credential already exists." }
        val id = ByteArray(8).also { SecureRandom().nextBytes(it) }.joinToString("") { "%02x".format(it) }
        return PairRequest(id, hash, name.take(60).replace(Regex("[\\p{C}]"), ""), host, now, Identity.verificationCode(fingerprint, token)).also { pending[id] = it }
    }
    @Synchronized fun expire() { pending.entries.removeAll { clock()-it.value.created > 120000 } }
    @Synchronized fun requests(): List<PairRequest> { expire(); return pending.values.toList() }
    @Synchronized fun approve(id: String) {
        expire()
        val request = pending[id] ?: error("Pairing request expired.")
        // Persist before granting access; storage failure must not grant an unremembered trust.
        val updated = trusted.toMutableMap().apply { put(request.hash, request.name) }
        repository.save(updated)
        trusted.putAll(updated); pending.remove(id)
    }
    @Synchronized fun reject(id: String) { pending.remove(id) }
    @Synchronized fun status(token: String): String {
        expire(); val hash = Identity.tokenHash(token)
        return if (hash in trusted) "paired" else if (pending.values.any { it.hash == hash }) "pending" else "expired"
    }
    @Synchronized fun authorize(token: String): String {
        require(Regex("[a-f0-9]{64}").matches(token)) { "Phone approval required." }
        val hash = Identity.tokenHash(token)
        require(hash in trusted) { "Phone approval required." }
        seen[hash] = clock()
        return hash
    }
    @Synchronized fun revoke(hash: String) {
        val updated = trusted.toMutableMap().apply { remove(hash) }
        repository.save(updated)
        trusted.remove(hash); seen.remove(hash); pending.entries.removeAll { it.value.hash == hash }
    }
    @Synchronized fun disconnect(hash: String) { seen.remove(hash) }
    @Synchronized fun devices(): List<Triple<String, String, Boolean>> = trusted.map { (hash, name) ->
        Triple(hash, name, seen.containsKey(hash) && clock()-(seen[hash] ?: 0) < 15000)
    }
}
