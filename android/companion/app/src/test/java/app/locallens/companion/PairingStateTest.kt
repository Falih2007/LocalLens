package app.locallens.companion

import org.junit.Assert.*
import org.junit.Test

class PairingStateTest {
    private class MemoryTrust: TrustRepository {
        var records = emptyMap<String, String>()
        var fails = false
        override fun load() = records.toMap()
        override fun save(records: Map<String, String>) { check(!fails); this.records = records.toMap() }
    }
    private val token = "ab".repeat(32)
    private fun rejected(block: () -> Unit) { try { block(); fail("Access was unexpectedly granted") } catch (_: IllegalArgumentException) {} }
    @Test fun verificationBindsTheCertificateAndExactRequestNotJustTheName() {
        val state = PairingState(MemoryTrust())
        val first = state.request(token, "Same laptop name", "192.168.1.20", "c".repeat(64))
        val second = state.request("ef".repeat(32), "Same laptop name", "192.168.1.20", "c".repeat(64))
        assertNotEquals(first.code, second.code)
        assertNotEquals(first.code, Identity.verificationCode("d".repeat(64), token))
        assertEquals(Identity.verificationCode("c".repeat(64), token), first.code)
        assertEquals("552F 8EFC 5EA9 A545", first.code) // Shared Python/Kotlin protocol vector.
    }
    @Test fun approvalPersistsOnlyHashAndRevocationSurvivesRestart() {
        val storage = MemoryTrust(); val state = PairingState(storage)
        val request = state.request(token, "Laptop", "192.168.1.20", "c".repeat(64))
        assertEquals("pending", state.status(token)); rejected { state.authorize(token) }
        state.approve(request.id)
        assertEquals("paired", state.status(token))
        assertFalse(storage.records.containsKey(token)); assertTrue(storage.records.containsKey(Identity.tokenHash(token)))
        val restarted = PairingState(storage)
        assertEquals("paired", restarted.status(token))
        restarted.authorize(token); restarted.revoke(Identity.tokenHash(token))
        assertEquals("expired", PairingState(storage).status(token)); rejected { restarted.authorize(token) }
    }
    @Test fun timeoutAndRejectionDoNotCreateTrust() {
        var now = 100000L; val storage = MemoryTrust(); val state = PairingState(storage) { now }
        val request = state.request(token, "Laptop", "192.168.1.20", "c".repeat(64))
        now += 120001
        assertEquals("expired", state.status(token))
        try { state.approve(request.id); fail() } catch (_: IllegalStateException) {}
        val next = state.request(token, "Laptop", "192.168.1.20", "c".repeat(64))
        state.reject(next.id); assertEquals("expired", state.status(token)); assertTrue(storage.records.isEmpty())
    }
    @Test fun failedPersistenceCannotGrantAuthorization() {
        val storage = MemoryTrust(); val state = PairingState(storage)
        val request = state.request(token, "Laptop", "192.168.1.20", "c".repeat(64))
        storage.fails = true
        try { state.approve(request.id); fail() } catch (_: IllegalStateException) {}
        rejected { state.authorize(token) }; assertTrue(storage.records.isEmpty())
    }
    @Test fun disconnectRetainsTrustButExpiresPresence() {
        val state = PairingState(MemoryTrust())
        state.approve(state.request(token, "Laptop", "192.168.1.20", "c".repeat(64)).id)
        val hash = state.authorize(token); assertTrue(state.devices().single().third)
        state.disconnect(hash); assertFalse(state.devices().single().third); assertEquals("paired", state.status(token))
    }
    @Test fun malformedCredentialsAndFloodAreRejected() {
        val state = PairingState(MemoryTrust())
        rejected { state.request("guess", "Laptop", "192.168.1.20", "c".repeat(64)) }
        repeat(5) { index -> state.request(index.toString(16).padStart(64, '0'), "Laptop", "192.168.1.20", "c".repeat(64)) }
        rejected { state.request("ff".repeat(32), "Laptop", "192.168.1.20", "c".repeat(64)) }
    }
}
