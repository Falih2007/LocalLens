package app.locallens.companion

import android.content.Context
import org.json.JSONObject

class AndroidTrustRepository(context: Context): TrustRepository {
    private val preferences = context.getSharedPreferences("locallens-trust", Context.MODE_PRIVATE)
    override fun load(): Map<String, String> {
        val json = JSONObject(preferences.getString("trusted", "{}") ?: "{}")
        return json.keys().asSequence().associateWith { json.getString(it) }
    }
    override fun save(records: Map<String, String>) {
        check(preferences.edit().putString("trusted", JSONObject(records as Map<*, *>).toString()).commit()) { "Could not save device trust." }
    }
}
