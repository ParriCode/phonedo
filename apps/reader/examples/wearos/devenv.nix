{ pkgs, lib, config, ... }:

{
  # ---------------------------------------------------------------------------
  # Reader Phonendo en Wear OS (OnePlus Watch 3) - entorno de desarrollo.
  #
  # Todo sale de Nix: JDK, Gradle, SDK, NDK, CMake y la imagen de Wear OS.
  # No se instala nada a mano (ni Android Studio, ni sdkmanager, ni imágenes
  # descargadas). Si Gradle pide un componente y muere con
  #   "The SDK directory is not writable (/nix/store/...)"
  # el arreglo es declararlo aquí, en el bloque `android`, con el nombre
  # exacto que da el mensaje. El SDK vive en el store y es de solo lectura.
  # ---------------------------------------------------------------------------

  packages = with pkgs; [
    git
    jq
    # Gradle 8.14 de nixpkgs: AGP 8.13 exige Gradle 8.13 o superior y aún no
    # soporta Gradle 9. Se usa `gradle` directamente, sin wrapper.
    gradle_8
    # Compilador del host para la prueba nativa del puente (tests/native).
    gcc
  ];

  # --- Java: AGP 8.x corre sobre JDK 17 ---------------------------------------
  languages.java = {
    enable = true;
    jdk.package = pkgs.jdk17;
  };

  # --- Android ----------------------------------------------------------------
  android = {
    enable = true;
    # compileSdk 36 (lo piden las androidx recientes); targetSdk 34, que es la
    # del OnePlus Watch 3 (Wear OS 5 = Android 14) y la de la imagen Wear OS.
    platforms.version = [ "34" "35" "36" ];
    # Imagen Wear OS para el emulador. Existe android-wear para API 33, 34 y
    # 35 en el repo.json fijado; 34 coincide con el reloj real. Ojo: androidenv
    # baja la imagen de cada plataforma declarada que la tenga, así que también
    # llega la de 35 (unos GB más); no hay de 36.
    systemImageTypes = [ "android-wear" ];
    abis = [ "x86_64" ];               # el host es x86_64; arm64 sería emulación lenta
    cmdLineTools.version = "11.0";
    tools.version = "26.1.1";
    platformTools.version = "37.0.1";   # 35.0.1 no existe en nixpkgs androidenv
    # La primera es la que usa aapt2 vía GRADLE_OPTS; 35.0.0 es la que AGP 8.13
    # usa por defecto para compilar.
    buildTools.version = [ "36.0.0" "35.0.0" ];
    emulator = {
      enable = true;
      version = "37.2.4";              # 35.1.4 no existe en nixpkgs androidenv
    };
    sources.enable = false;
    systemImages.enable = true;
    ndk.enable = true;
    # El mismo NDK que fija app/build.gradle.kts (ndkVersion). La primera de la
    # lista es la que devenv exporta como ANDROID_NDK_ROOT y escribe en
    # local.properties como ndk.dir: si no coinciden, Gradle intenta instalar
    # la suya y muere con "SDK directory is not writable".
    ndk.version = [ "27.0.12077973" ];
    # CMake para externalNativeBuild; la misma versión que fija el build.
    cmake.version = [ "3.22.1" ];
    googleAPIs.enable = false;
    googleTVAddOns.enable = false;
    extras = [ ];
    extraLicenses = [
      "android-sdk-preview-license"
      "android-googletv-license"
      "android-sdk-arm-dbt-license"
      "google-gdk-license"
      "intel-android-extra-license"
      "intel-android-sysimage-license"
      "mips-android-sysimage-license"
    ];
  };

  env = {
    # El locale-archive que trae devenv solo incluye en_US.utf8; con
    # LANG=es_ES.UTF-8 bash avisa "setlocale: cannot change locale".
    LOCALE_ARCHIVE = "${pkgs.glibcLocales.override {
      allLocales = false;
      locales = [ "es_ES.UTF-8/UTF-8" "en_US.UTF-8/UTF-8" ];
    }}/lib/locale/locale-archive";
  };

  # --- Comandos disponibles dentro del shell ----------------------------------
  scripts = {
    # APK debug en app/build/outputs/apk/debug/app-debug.apk.
    build.exec = ''
      cd "$DEVENV_ROOT" && gradle assembleDebug "$@"
    '';

    # Pruebas JVM de la parte pura en Kotlin (HTTP, SSE, cuerpo de /newEvent).
    unit.exec = ''
      cd "$DEVENV_ROOT" && gradle testDebugUnitTest "$@"
    '';

    # Prueba del puente C++ sin JNI, compilado con g++ en el host.
    native-test.exec = ''
      bash "$DEVENV_ROOT/tests/native/run.sh" "$@"
    '';

    # Instala el APK en lo que vea adb. Con varios dispositivos (reloj y
    # emulador a la vez) elige uno: instalar -s <serie>, o ANDROID_SERIAL=<serie>.
    instalar.exec = ''
      APK="$DEVENV_ROOT/app/build/outputs/apk/debug/app-debug.apk"
      [ -f "$APK" ] || { echo "No hay APK: ejecuta 'build' primero." >&2; exit 1; }
      adb "$@" install -r "$APK"
    '';

    # Logcat de la app: por PID si está corriendo, si no por la etiqueta.
    logs.exec = ''
      PID=$(adb "$@" shell pidof -s org.phonendo.reader.wearos 2>/dev/null | tr -d '\r')
      if [ -n "$PID" ]; then
        adb "$@" logcat --pid="$PID"
      else
        echo "La app no está corriendo; filtrando por la etiqueta PhonendoReader." >&2
        adb "$@" logcat -s PhonendoReader:V
      fi
    '';

    # Depuración por Wi-Fi del reloj (no tiene USB de datos).
    pair.exec = ''
      if [ $# -lt 1 ]; then
        echo "En el reloj: Ajustes > Sistema > Información > toca 'Número de compilación'"
        echo "siete veces; luego Ajustes > Opciones de desarrollador > Depuración"
        echo "inalámbrica > Emparejar dispositivo nuevo."
        echo ""
        echo "  pair <ip>:<puerto-de-emparejado> [código]   empareja una vez"
        echo "  adb connect <ip>:<puerto-de-depuracion>     conecta (puerto distinto)"
        echo "  adb devices                                 debe aparecer el reloj"
        exit 0
      fi
      adb pair "$@"
    '';

    # Crea el AVD de Wear OS si falta. Idempotente: si existe, no toca nada.
    # La imagen la provee Nix (android.systemImages) y el AVD nace en
    # ./.android/avd: devenv apunta ahí ANDROID_USER_HOME y ANDROID_AVD_HOME.
    avd.exec = ''
      # Mismo arreglo de libc++ que en 'emu' (ver el comentario de abajo):
      # sin esto, 'emulator -list-avds' muere con symbol lookup error.
      export LD_LIBRARY_PATH="$ANDROID_HOME/emulator/lib64''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

      NAME="''${1:-phonendo-wear}"
      if emulator -list-avds 2>/dev/null | grep -qx "$NAME"; then
        echo "El AVD '$NAME' ya existe."
        exit 0
      fi
      IMG="system-images;android-34;android-wear;x86_64"
      if [ ! -d "$ANDROID_HOME/system-images/android-34/android-wear" ]; then
        echo "Falta la imagen de Wear OS en el SDK." >&2
        echo "Revisa android.systemImageTypes / abis en devenv.nix." >&2
        exit 1
      fi
      echo "Creando el AVD '$NAME' desde $IMG..."
      echo no | avdmanager create avd -n "$NAME" -k "$IMG" -d wearos_large_round --force
      echo "Listo. Arráncalo con: emu"
    '';

    emu.exec = ''
      # devenv pone build-tools/*/lib64 y la lib del NDK en LD_LIBRARY_PATH, y
      # esa libc++ no exporta los símbolos que pide libabseil_dll.so del
      # emulador. LD_LIBRARY_PATH gana al RUNPATH del binario, así que el
      # emulador carga la libc++ equivocada y muere con "symbol lookup error".
      # Anteponer la suya propia lo arregla.
      export LD_LIBRARY_PATH="$ANDROID_HOME/emulator/lib64''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

      AVD=$(emulator -list-avds | head -n1)
      if [ -z "$AVD" ]; then
        echo "No hay ningún AVD; creando uno..." >&2
        avd || exit 1
        AVD=$(emulator -list-avds | head -n1)
        [ -n "$AVD" ] || { echo "No se pudo crear el AVD." >&2; exit 1; }
      fi
      echo "Arrancando $AVD..."
      emulator -avd "$AVD" -netdelay none -netspeed full &
    '';
  };

  enterShell = ''
    echo ""
    echo "  Reader Phonendo Wear OS - entorno listo"
    echo ""
    echo "  build          compila el APK debug"
    echo "  unit           pruebas JVM de la parte Kotlin"
    echo "  native-test    prueba del puente C++ en el host"
    echo "  instalar       instala el APK (instalar -s <serie> si hay varios)"
    echo "  logs           logcat de la app"
    echo "  pair           depuración por Wi-Fi del reloj"
    echo "  avd / emu      crea y arranca el emulador Wear OS"
    echo ""
  '';

  enterTest = ''
    java -version 2>&1 | head -n1 | grep -q '"17' || (echo "Se esperaba JDK 17" && exit 1)
    gradle --version | grep -q "^Gradle 8" || (echo "Se esperaba Gradle 8" && exit 1)
  '';
}
