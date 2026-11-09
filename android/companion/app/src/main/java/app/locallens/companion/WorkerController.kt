package app.locallens.companion

import org.json.JSONObject

/** Deliberately no imported Termux executable: Android app sandbox/ABI/linker differ.
 * A future JNI adapter must use this exact revision and loopback-only RPC, gated by trust.
 * Pairing-only APK cannot honestly mark an unbundled worker ready. */
class WorkerController {
    val revision = "39febd2adb947b70da35e95f9351b3bf58ad170a"
    val ready = false
    val reason = "Native RPC worker is not bundled in this pairing preview. Phone compute is unavailable in this preview."
    fun stop() = Unit
    fun runtime(): JSONObject = JSONObject().put("backend", "llama.cpp RPC").put("status", "unavailable")
        .put("expected_revision", revision).put("build_record_revision", JSONObject.NULL).put("reason", reason)
}
