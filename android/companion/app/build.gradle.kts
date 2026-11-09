plugins { id("com.android.application") }

android {
    namespace = "app.locallens.companion"
    compileSdk = 37
    defaultConfig {
        applicationId = "app.locallens.companion"
        minSdk = 26
        targetSdk = 35
        versionCode = 3
        versionName = "0.3.2-pairing-preview"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildTypes { getByName("release") { isMinifyEnabled = false } }
}

dependencies { testImplementation("junit:junit:4.13.2") }
