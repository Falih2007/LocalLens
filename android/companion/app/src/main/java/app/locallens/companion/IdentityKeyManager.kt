package app.locallens.companion

import java.net.Socket
import java.security.PrivateKey
import java.security.Principal
import java.security.cert.X509Certificate
import javax.net.ssl.SSLEngine
import javax.net.ssl.X509ExtendedKeyManager

/** Only the current certificate is eligible, even if old RSA aliases remain in Keystore. */
class IdentityKeyManager(private val alias: String, private val key: PrivateKey, private val chain: Array<X509Certificate>): X509ExtendedKeyManager() {
    private fun matches(type: String?) = type == key.algorithm || type == "${key.algorithm}_${key.algorithm}"
    override fun getPrivateKey(selected: String?) = if (selected == alias) key else null
    override fun getCertificateChain(selected: String?) = if (selected == alias) chain.copyOf() else null
    override fun getServerAliases(type: String?, issuers: Array<out Principal>?) = if (matches(type)) arrayOf(alias) else null
    override fun chooseServerAlias(type: String?, issuers: Array<out Principal>?, socket: Socket?) = if (matches(type)) alias else null
    override fun chooseEngineServerAlias(type: String?, issuers: Array<out Principal>?, engine: SSLEngine?) = if (matches(type)) alias else null
    override fun getClientAliases(type: String?, issuers: Array<out Principal>?) = null
    override fun chooseClientAlias(types: Array<out String>?, issuers: Array<out Principal>?, socket: Socket?) = null
}
