// Proyecto Gradle del Reader Phonendo para Wear OS. Gradle sale de devenv
// (gradle_8 de nixpkgs), por eso no hay wrapper: se ejecuta `gradle` o los
// scripts `build` y `unit` dentro de `devenv shell`.
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "phonendo-reader-wearos"
include(":app")
