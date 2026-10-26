// App Wear OS del Reader. La configuración (Managers, tokens, puerto) sale de
// secrets.properties, fuera de git, y entra en BuildConfig: igual que el
// secrets.h del ESP32, si falta el archivo la compilación se para con un
// mensaje que dice cómo crearlo.
import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

val secretsFile = rootProject.file("secrets.properties")
if (!secretsFile.isFile) {
    throw GradleException(
        "Falta secrets.properties: copia secrets.example.properties a secrets.properties " +
            "(en ${rootProject.projectDir}) y rellena tus credenciales."
    )
}
val secrets = Properties().apply { secretsFile.inputStream().use { load(it) } }

fun secret(name: String, default: String = ""): String = secrets.getProperty(name, default).trim()

// Literal Java para buildConfigField.
fun javaString(value: String): String =
    "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\""

val readerPort = secret("READER_PORT", "8080").ifEmpty { "8080" }
if (readerPort.toIntOrNull() !in 1..65535) {
    throw GradleException("READER_PORT en secrets.properties debe ser un puerto entre 1 y 65535.")
}

android {
    namespace = "org.phonendo.reader.wearos"
    compileSdk = 36
    // Debe coincidir con android.ndk.version y android.cmake.version de
    // devenv.nix; si no, Gradle intenta instalarlos en el SDK de solo lectura.
    ndkVersion = "27.0.12077973"

    defaultConfig {
        applicationId = "org.phonendo.reader.wearos"
        // Wear OS 3 (API 30) es el mínimo de Health Services; el OnePlus
        // Watch 3 lleva Wear OS 5 (API 34).
        minSdk = 30
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        buildConfigField("String", "READER_ID", javaString(secret("READER_ID", "reader-wearos-01")))
        buildConfigField("int", "READER_PORT", readerPort)
        buildConfigField("String", "READER_TOKEN", javaString(secret("READER_TOKEN")))
        buildConfigField("String", "MANAGER_URLS", javaString(secret("MANAGER_URLS")))
        buildConfigField("String", "MANAGER_TOKEN", javaString(secret("MANAGER_TOKEN")))

        ndk {
            // El OnePlus Watch 3 (Snapdragon W5) corre Wear OS de 32 bits:
            // armeabi-v7a. arm64 para otros relojes, x86_64 para el emulador.
            abiFilters += listOf("armeabi-v7a", "arm64-v8a", "x86_64")
        }
    }

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
            version = "3.22.1"
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.wear.compose.material)
    implementation(libs.wear.compose.foundation)
    implementation(libs.health.services)
    implementation(libs.guava)
    implementation(libs.kotlinx.coroutines.android)

    testImplementation(libs.junit)
}
