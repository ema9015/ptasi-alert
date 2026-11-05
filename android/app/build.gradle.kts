plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Adres strony z mapą i danymi (GitHub Pages) – przekazywany przez workflow ze zmiennej STRONA_URL
val siteUrl = (System.getenv("STRONA_URL")?.trim()?.takeIf { it.isNotEmpty() } ?: "https://example.github.io/ptasi-alert/")
    .let { if (it.endsWith("/")) it else "$it/" }
val runNumber = (System.getenv("GITHUB_RUN_NUMBER") ?: "1").toInt()
val keystorePath: String? = System.getenv("KEYSTORE_FILE")

android {
    namespace = "pl.ptasialert"
    compileSdk = 34

    defaultConfig {
        applicationId = "pl.ptasialert"
        minSdk = 26
        targetSdk = 34
        versionCode = runNumber
        versionName = "1.$runNumber"
        buildConfigField("String", "SITE_URL", "\"$siteUrl\"")
    }

    buildFeatures { buildConfig = true }

    signingConfigs {
        if (keystorePath != null && file(keystorePath).exists()) {
            create("release") {
                storeFile = file(keystorePath)
                storePassword = System.getenv("KEYSTORE_PASSWORD")
                keyAlias = System.getenv("KEY_ALIAS")
                keyPassword = System.getenv("KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release") ?: signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    lint {
        checkReleaseBuilds = false
        abortOnError = false
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.work:work-runtime-ktx:2.9.1")
}
